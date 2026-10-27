import frappe
from frappe.tests import IntegrationTestCase

from ubc_solar.merch import store
from ubc_solar.merch.doctype.merch_order.merch_order import cancel_order, fulfil, mark_paid, mark_ready
from ubc_solar.merch.doctype.merch_product.merch_product import make_restock_request
from ubc_solar.money.budget import get_budget_summary
from ubc_solar.tests.test_cars_money import make_budget
from ubc_solar.tests.utils import add_stock, as_user, make_member, stock_qty, unique


def make_product(options=("S", "M"), stock=5, **kw):
	product = frappe.get_doc(
		{
			"doctype": "Merch Product",
			"product_name": unique("Hoodie"),
			"status": "On Sale",
			"public_price": 50,
			"team_price": 35,
			"variants": [{"option_label": o} for o in options],
			**kw,
		}
	).insert(ignore_permissions=True)
	for v in product.variants:
		if stock:
			add_stock(v.item_code, stock, store.merch_location(), rate=20)
	return product


def store_order(product, option="M", qty=1, **kw):
	return store.place_order(
		buyer_name=kw.pop("buyer_name", "Pat Buyer"),
		email=kw.pop("email", "pat@example.com"),
		items=[{"product": product.name, "option": option, "qty": qty}],
		**kw,
	)


class TestMerch(IntegrationTestCase):
	def setUp(self):
		frappe.db.set_single_value("Merch Settings", "store_open", 1)
		frappe.db.set_single_value("Merch Settings", "merch_counts_as_raised", 1)
		frappe.clear_document_cache("Merch Settings", "Merch Settings")

	def test_install_sets_up_merch(self):
		settings = store.settings()
		self.assertTrue(frappe.db.exists("Warehouse", settings.merch_location))
		self.assertTrue(frappe.db.exists("Item Group", settings.group_merch))
		self.assertIn("Merch", frappe.get_meta("Stock Entry").get_field("solar_source").options.split("\n"))

	def test_each_option_is_a_stock_item(self):
		product = make_product(stock=0)
		self.assertEqual([v.option_label for v in product.variants], ["S", "M"])
		for v in product.variants:
			item = frappe.get_doc("Item", v.item_code)
			self.assertEqual(item.item_group, store.settings().group_merch)
			self.assertEqual(item.item_name, f"{product.product_name} ({v.option_label})")
		single = make_product(options=(), stock=0)
		self.assertEqual([v.option_label for v in single.variants], ["One size"])
		with self.assertRaises(frappe.ValidationError):
			make_product(options=("M", "M"), stock=0)

	def test_guest_order_pays_public_price_and_reserves_stock(self):
		product = make_product(stock=3, max_per_order=3)
		with as_user("Guest"):
			result = store_order(product, qty=2)
			catalog = {p.name: p for p in store.catalog(is_team=False)}
		order = frappe.get_doc("Merch Order", result["name"])
		self.assertEqual((order.status, order.source, order.team_member), ("Placed", "Online store", None))
		self.assertEqual((order.items[0].rate, order.total), (50, 100))
		self.assertEqual(catalog[product.name].price, 50)
		item_m = order.items[0].item_code
		self.assertEqual(store.available_qty(item_m), 1)
		with as_user("Guest"), self.assertRaises(frappe.ValidationError):
			store_order(product, qty=2)  # only 1 left
		with as_user("Guest"), self.assertRaises(frappe.ValidationError):
			store_order(product, option="S", qty=4)  # more than 3 per order
		with as_user("Guest"), self.assertRaises(frappe.ValidationError):
			store_order(product, option="XL")

	def test_team_member_gets_team_price_and_team_only_items(self):
		member = make_member(subteam="Aeroshell")
		team_only = make_product(sold_to="Team only")
		with as_user("Guest"):
			self.assertNotIn(team_only.name, [p.name for p in store.catalog(is_team=False)])
			with self.assertRaises(frappe.ValidationError):
				store_order(team_only)
		with as_user(member.user):
			# The buyer can't claim the team price by typing a member's email; it comes from the login.
			result = store_order(team_only, buyer_name="", email="")
		order = frappe.get_doc("Merch Order", result["name"])
		self.assertEqual(order.team_member, member.name)
		self.assertEqual((order.buyer_name, order.email), (member.full_name, member.email))
		self.assertEqual(order.total, 35)

		public = make_product()
		with as_user("Guest"):
			guest = frappe.get_doc("Merch Order", store_order(public, email=member.email)["name"])
		self.assertEqual((guest.team_member, guest.total), (None, 50))

	def test_closed_store_and_unlisted_products(self):
		product = make_product()
		draft = make_product(status="Draft")
		with as_user("Guest"), self.assertRaises(frappe.ValidationError):
			store_order(draft)
		frappe.db.set_single_value("Merch Settings", "store_open", 0)
		frappe.clear_document_cache("Merch Settings", "Merch Settings")
		with as_user("Guest"), self.assertRaises(frappe.ValidationError):
			store_order(product)

	def test_preorder_allows_ordering_without_stock(self):
		product = make_product(stock=0, allow_preorder=1)
		with as_user("Guest"):
			self.assertIn(product.name, [p.name for p in store.catalog(is_team=False)])
			order = frappe.get_doc("Merch Order", store_order(product, qty=2)["name"])
		mark_paid(order.name, "Cash")
		with self.assertRaises(frappe.ValidationError):
			fulfil(order.name)  # nothing to hand over yet
		add_stock(order.items[0].item_code, 2, store.merch_location())
		fulfil(order.name)
		self.assertEqual(frappe.db.get_value("Merch Order", order.name, "status"), "Fulfilled")

	def test_paid_order_counts_toward_budget_and_leaves_stock(self):
		budget = make_budget([("Merch", "Business", 100)])
		product = make_product(stock=5)
		order = frappe.get_doc(
			{
				"doctype": "Merch Order",
				"buyer_name": "Walk-in",
				"budget": budget,
				"items": [{"product": product.name, "option_label": "S", "qty": 2}],
			}
		).insert()
		self.assertEqual((order.source, order.total), ("In person", 100))
		raised = get_budget_summary(budget)["raised"]

		with self.assertRaises(frappe.ValidationError):
			fulfil(order.name)  # not paid yet
		mark_paid(order.name, "E-transfer", "REF123")
		order.reload()
		self.assertEqual((order.status, order.payment_reference), ("Paid", "REF123"))
		entry = frappe.get_doc("Funding Entry", order.funding_entry)
		self.assertEqual((entry.source_type, entry.status, entry.amount), ("Merch Sales", "Received", 100))
		self.assertEqual(get_budget_summary(budget)["raised"], raised + 100)

		mark_ready(order.name)
		item = order.items[0].item_code
		fulfil(order.name)
		order.reload()
		self.assertEqual(order.status, "Fulfilled")
		self.assertEqual(stock_qty(item, store.merch_location()), 3)
		se = frappe.get_doc("Stock Entry", order.stock_entry)
		self.assertEqual((se.solar_source, se.solar_reference_name), ("Merch", order.name))

		cancel_order(order.name, "Wrong size")
		order.reload()
		self.assertEqual(order.status, "Cancelled")
		self.assertIn("Wrong size", order.notes)
		self.assertEqual(stock_qty(item, store.merch_location()), 5)
		self.assertEqual(frappe.db.get_value("Funding Entry", entry.name, "status"), "Refunded")
		self.assertEqual(get_budget_summary(budget)["raised"], raised)
		with self.assertRaises(frappe.ValidationError):
			cancel_order(order.name)

	def test_sales_can_be_kept_out_of_the_budget(self):
		frappe.db.set_single_value("Merch Settings", "merch_counts_as_raised", 0)
		frappe.clear_document_cache("Merch Settings", "Merch Settings")
		product = make_product()
		order = frappe.get_doc(
			{"doctype": "Merch Order", "buyer_name": "Walk-in", "items": [{"product": product.name, "option_label": "M", "qty": 1}]}
		).insert()
		mark_paid(order.name, "Cash")
		self.assertFalse(frappe.db.get_value("Merch Order", order.name, "funding_entry"))

	def test_status_and_items_only_change_through_actions(self):
		product = make_product()
		order = frappe.get_doc(
			{"doctype": "Merch Order", "buyer_name": "Walk-in", "items": [{"product": product.name, "option_label": "M", "qty": 1}]}
		).insert()
		order.status = "Fulfilled"
		order.save()
		self.assertEqual(order.status, "Placed")

		order.items[0].qty = 2
		order.save()
		self.assertEqual(order.total, 100)
		mark_paid(order.name, "Cash")
		order.reload()
		order.items[0].qty = 3
		with self.assertRaises(frappe.ValidationError):
			order.save()

	def test_only_merch_managers_handle_orders(self):
		product = make_product()
		with as_user("Guest"):
			name = store_order(product)["name"]
		member = make_member(subteam="Aeroshell")
		with as_user(member.user), self.assertRaises(frappe.PermissionError):
			mark_paid(name, "Cash")
		manager = make_member(subteam="Aeroshell")
		manager.append("extra_access", {"role_profile": "Merch Manager Access"})
		with as_user("Administrator"):
			manager.save()
		with as_user(manager.user):
			mark_paid(name, "Cash")
			self.assertTrue(frappe.has_permission("Merch Settings", "write"))
		self.assertEqual(frappe.db.get_value("Merch Order", name, "status"), "Paid")
		self.assertIn(manager.user, store.merch_managers())

	def test_restock_request_goes_to_merch_location(self):
		product = make_product(stock=0)
		mr = make_restock_request(product.name)
		self.assertEqual(mr["material_request_type"], "Purchase")
		self.assertEqual({row["item_code"] for row in mr["items"]}, {v.item_code for v in product.variants})
		self.assertEqual({row["warehouse"] for row in mr["items"]}, {store.merch_location()})
