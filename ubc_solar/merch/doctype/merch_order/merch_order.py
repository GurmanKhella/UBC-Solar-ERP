# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

"""A merch order: Placed -> Paid -> Ready for Pickup -> Fulfilled (or Cancelled).

Paying records the money as a Funding Entry (source Merch Sales) on the active
budget, so it counts toward Raised (Merch Settings). Handing it over takes
the items out of the merch stock location. Cancelling marks the Funding Entry
Refunded and, if the items were already handed over, puts them back in stock.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, fmt_money, nowdate, validate_email_address

from ubc_solar.merch import store

OPEN = ("Placed", "Paid", "Ready for Pickup")


class MerchOrder(Document):
	def validate(self):
		self.buyer_name = (self.buyer_name or "").strip()
		self.email = (self.email or "").strip()
		if self.flags.from_store:
			self.source = "Online store"
			self.status = "Placed"
			self.team_member = store.team_member_for_session()
		self.check_status_change()
		if self.team_member:
			member = frappe.db.get_value("Team Member", self.team_member, ["full_name", "email"], as_dict=True)
			self.buyer_name = self.buyer_name or member.full_name
			self.email = self.email or member.email
		if self.flags.from_store and not self.email:
			frappe.throw(_("Enter your email so we can tell you when your order is ready."))
		if self.email:
			validate_email_address(self.email, throw=True)
		if not self.buyer_name:
			frappe.throw(_("Enter the buyer's name."))
		self.order_date = self.order_date or nowdate()
		if not self.budget:
			from ubc_solar.money.budget import active_budget

			self.budget = active_budget()
		if self.is_new() or self.items_changed():
			self.check_items()
		self.total = sum(flt(row.amount) for row in self.items)

	def check_status_change(self):
		"""Status only moves through the actions below, so stock and money stay in step."""
		if self.is_new():
			self.status = "Placed"
			self.paid_on = self.funding_entry = self.stock_entry = None
			return
		before = self.get_doc_before_save()
		if before and not self.flags.status_action:
			for field in ("status", "paid_on", "funding_entry", "stock_entry"):
				self.set(field, before.get(field))

	def items_changed(self):
		before = self.get_doc_before_save()
		if not before:
			return True

		def key(doc):
			return [(r.product, r.option_label, cint(r.qty)) for r in doc.items]

		if key(before) == key(self) and before.team_member == self.team_member:
			return False
		if before.status != "Placed":
			frappe.throw(_("Items can only be changed before the order is paid."))
		return True

	def check_items(self):
		"""Fill in the stock item and price for each row, and check what's allowed."""
		if not self.items:
			frappe.throw(_("Add at least one item."))
		is_team = bool(self.team_member)
		wanted = {}
		products = {}
		for row in self.items:
			product = products.get(row.product) or frappe.get_doc("Merch Product", row.product)
			products[row.product] = product
			if product.status != "On Sale":
				frappe.throw(_("{0} isn't on sale.").format(product.product_name))
			if product.sold_to == "Team only" and not is_team:
				frappe.throw(_("{0} is only sold to team members (log in first).").format(product.product_name))
			options = [v for v in product.variants if v.enabled]
			if not row.option_label and len(options) == 1:
				row.option_label = options[0].option_label
			variant = next((v for v in options if v.option_label == (row.option_label or "").strip()), None)
			if not variant:
				frappe.throw(_("Pick an option for {0} ({1}).").format(product.product_name, ", ".join(v.option_label for v in options)))
			row.option_label = variant.option_label
			row.item_code = variant.item_code
			row.qty = cint(row.qty)
			if row.qty <= 0:
				frappe.throw(_("Quantities must be at least 1."))
			row.rate = store.price_for(product, is_team)
			row.amount = row.rate * row.qty
			wanted.setdefault(row.item_code, [product, variant, 0])[2] += row.qty

		for product in products.values():
			count = sum(cint(r.qty) for r in self.items if r.product == product.name)
			if cint(product.max_per_order) and count > cint(product.max_per_order):
				frappe.throw(_("At most {0} of {1} per order.").format(product.max_per_order, product.product_name))

		for item_code, (product, variant, qty) in wanted.items():
			if product.allow_preorder:
				continue
			available = store.available_qty(item_code, exclude_order=None if self.is_new() else self.name)
			if qty > available:
				frappe.throw(
					_("Only {0} of {1} ({2}) left.").format(cint(max(available, 0)), product.product_name, variant.option_label)
				)

	def after_insert(self):
		from ubc_solar.solar_automation import notify

		notify.send(
			"Merch order",
			_("New merch order from {0} ({1}).").format(self.buyer_name, fmt_money(self.total, currency="CAD")),
			doc=self,
			users=store.merch_managers(),
		)
		if self.flags.from_store and self.email:
			settings = store.settings()
			email_buyer(
				self,
				_("UBC Solar merch order {0}").format(self.name),
				[
					_("Thanks for your order! Total: {0}.").format(fmt_money(self.total, currency="CAD")),
					settings.payment_instructions,
					settings.pickup_info,
				],
			)

	def require(self, *statuses):
		if self.status not in statuses:
			frappe.throw(_("This order is {0}.").format(self.status))


def email_buyer(order, subject, paragraphs):
	"""Email the buyer, if the ERP has an outgoing email account set up. Never blocks the order."""
	if not frappe.db.exists("Email Account", {"default_outgoing": 1, "enable_outgoing": 1}):
		return
	lines = "".join(f"<p>{frappe.utils.escape_html(p)}</p>" for p in paragraphs if p)
	items = "".join(
		f"<li>{cint(r.qty)} × {frappe.utils.escape_html(r.product)} ({frappe.utils.escape_html(r.option_label)})</li>"
		for r in order.items
	)
	try:
		frappe.sendmail(
			recipients=[order.email],
			subject=subject,
			message=f"{lines}<ul>{items}</ul><p>{_('Order')}: {order.name}</p>",
			reference_doctype=order.doctype,
			reference_name=order.name,
		)
	except Exception:
		frappe.log_error(f"Couldn't email merch order {order.name}")


def _get(order):
	doc = frappe.get_doc("Merch Order", order)
	doc.check_permission("write")
	doc.flags.status_action = True
	return doc


@frappe.whitelist()
def mark_paid(order: str, payment_method: str, payment_reference: str | None = None):
	doc = _get(order)
	doc.require("Placed", "Ready for Pickup")
	if doc.paid_on:
		frappe.throw(_("This order is already paid."))
	if not payment_method:
		frappe.throw(_("Pick how they paid."))
	doc.payment_method = payment_method
	doc.payment_reference = (payment_reference or "").strip()
	doc.paid_on = nowdate()
	if doc.status == "Placed":
		doc.status = "Paid"
	if cint(store.settings().merch_counts_as_raised) and flt(doc.total) > 0 and doc.budget:
		entry = frappe.get_doc(
			{
				"doctype": "Funding Entry",
				"budget": doc.budget,
				"source_type": "Merch Sales",
				"source_name": _("Merch order {0} ({1})").format(doc.name, doc.buyer_name)[:140],
				"amount": doc.total,
				"status": "Received",
				"date": nowdate(),
				"received_on": nowdate(),
			}
		)
		entry.insert(ignore_permissions=True)
		doc.funding_entry = entry.name
	doc.save()
	return doc.status


@frappe.whitelist()
def mark_ready(order: str):
	"""Packed and waiting at pickup. Emails the buyer."""
	doc = _get(order)
	doc.require("Placed", "Paid")
	doc.status = "Ready for Pickup"
	doc.save()
	if doc.email:
		email_buyer(
			doc,
			_("Your UBC Solar merch order {0} is ready").format(doc.name),
			[
				_("Your order is ready for pickup."),
				store.settings().pickup_info,
				None if doc.paid_on else store.settings().payment_instructions,
			],
		)
	return doc.status


@frappe.whitelist()
def fulfil(order: str):
	"""Handed to the buyer: take the items out of merch stock."""
	doc = _get(order)
	doc.require("Paid", "Ready for Pickup")
	if not doc.paid_on:
		frappe.throw(_("Mark the order paid before handing it over."))
	location = store.merch_location()
	needed = {}
	for row in doc.items:
		needed[row.item_code] = needed.get(row.item_code, 0) + cint(row.qty)
	short = [
		f"{frappe.db.get_value('Item', code, 'item_name')} ({cint(store.variant_stock(code))} of {qty})"
		for code, qty in needed.items()
		if store.variant_stock(code) < qty
	]
	if short:
		frappe.throw(_("Not enough in {0}: {1}. Receive more stock first.").format(location, ", ".join(short)))

	from ubc_solar.solar_inventory.stock import make_stock_entry

	se = make_stock_entry(
		"Material Issue",
		[{"item_code": code, "qty": qty, "s_warehouse": location} for code, qty in needed.items()],
		source="Merch",
		reference=doc,
	)
	doc.stock_entry = se.name
	doc.status = "Fulfilled"
	doc.save()
	return doc.status


@frappe.whitelist()
def cancel_order(order: str, reason: str | None = None):
	"""Cancel (and refund). Items already handed over go back into merch stock."""
	doc = _get(order)
	doc.require(*OPEN, "Fulfilled")
	if doc.stock_entry and frappe.db.get_value("Stock Entry", doc.stock_entry, "docstatus") == 1:
		se = frappe.get_doc("Stock Entry", doc.stock_entry)
		se.flags.ignore_permissions = True
		se.cancel()
	if doc.funding_entry:
		frappe.db.set_value("Funding Entry", doc.funding_entry, "status", "Refunded")
	doc.status = "Cancelled"
	if reason:
		doc.notes = "\n".join(p for p in (doc.notes, _("Cancelled: {0}").format(reason.strip())) if p)
	doc.save()
	return doc.status
