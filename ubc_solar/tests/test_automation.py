import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from ubc_solar.solar_automation import drive, lookup, monday, notify, slack, wiki
from ubc_solar.tests.test_cars_money import make_budget, make_car, make_project
from ubc_solar.tests.utils import add_stock, make_item, make_location, make_member, unique


def enable(**values):
	settings = frappe.get_doc("Solar Settings")
	settings.update(values)
	settings.flags.ignore_permissions = True
	settings.save()
	frappe.clear_document_cache("Solar Settings", "Solar Settings")


class FakeResponse:
	def __init__(self, data):
		self.data = data
		self.status_code = 200

	def raise_for_status(self):
		pass

	def json(self):
		return self.data


class TestSlack(IntegrationTestCase):
	def setUp(self):
		enable(slack_enabled=1, slack_bot_token="xoxb-test", slack_signing_secret="secret", default_channel="#general")

	def tearDown(self):
		enable(slack_enabled=0, wiki_enabled=0, drive_enabled=0, monday_enabled=0)

	def test_notification_goes_to_subteam_channel_with_mentions(self):
		lead = make_member("Subteam Lead", subteam="Embedded")
		frappe.db.set_value("Team Member", lead.name, "slack_user_id", "U123")
		frappe.db.set_value("Subteam", "Embedded", "slack_channel", "#embedded")
		frappe.clear_cache(doctype="Subteam")
		car = make_car()
		with patch("frappe.enqueue") as enqueue:
			notify.send("BOM ready for review", "BOM ready for review.", car, users=[lead.user], subteam="Embedded")
		kwargs = enqueue.call_args.kwargs
		self.assertEqual(kwargs["channel"], "#embedded")
		self.assertIn("<@U123>", kwargs["text"])
		self.assertIn("BOM ready for review.", kwargs["text"])
		self.assertIn(car.name, kwargs["text"])

	def test_route_table_and_default(self):
		settings = frappe.get_doc("Solar Settings")
		settings.append("slack_routes", {"event": "Parts arrived", "channel": "#parts"})
		settings.save()
		frappe.clear_document_cache("Solar Settings", "Solar Settings")
		self.assertEqual(notify.channel_for("Parts arrived"), "#parts")
		self.assertEqual(notify.channel_for("Expiring soon"), "#general")

	def test_post_job_logs_success_and_failure(self):
		with patch("ubc_solar.solar_automation.slack.requests.post", return_value=FakeResponse({"ok": True})) as post:
			slack.post_job("#general", "hello", event="test")
		self.assertEqual(post.call_args.kwargs["json"]["channel"], "#general")
		self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer xoxb-test")
		with patch("ubc_solar.solar_automation.slack.requests.post", return_value=FakeResponse({"ok": False, "error": "channel_not_found"})):
			slack.post_job("#nope", "hello", event="test")
		last = frappe.get_all("Solar Automation Log", fields=["status", "message"], order_by="creation desc", limit=1)[0]
		self.assertEqual(last.status, "Failed")
		self.assertIn("channel_not_found", last.message)

	def test_member_linked_to_slack_by_email(self):
		member = make_member("Member", subteam="Business")
		with patch("ubc_solar.solar_automation.slack.requests.post", return_value=FakeResponse({"ok": True, "user": {"id": "U999"}})):
			slack.link_member_to_slack(member.name)
		self.assertEqual(frappe.db.get_value("Team Member", member.name, "slack_user_id"), "U999")

	def test_signature_check(self):
		body = "command=%2Ferp&text=help"
		ts = str(int(time.time()))
		good = "v0=" + hmac.new(b"secret", f"v0:{ts}:{body}".encode(), hashlib.sha256).hexdigest()
		request = MagicMock()
		request.headers = {"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": good}
		request.get_data.return_value = body
		with patch.object(frappe, "request", request, create=True):
			self.assertTrue(slack.verify_request("secret"))
			request.headers = {"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": "v0=bad"}
			self.assertFalse(slack.verify_request("secret"))
			request.headers = {"X-Slack-Request-Timestamp": str(int(time.time()) - 3600), "X-Slack-Signature": good}
			self.assertFalse(slack.verify_request("secret"))


class TestLookup(IntegrationTestCase):
	def test_answers(self):
		shelf = make_location(unique("E-L"))
		tag = unique("BOLT")
		bolt = make_item("Buy", mpn=tag, item_name=f"M5 bolt {tag}")
		add_stock(bolt.name, 34, shelf)
		self.assertIn("34", lookup.answer(f"part {tag}"))
		self.assertIn(shelf, lookup.answer(f"part {tag}"))
		budget = make_budget([("Battery Management", "Battery Management", 3000)])
		self.assertIn("3,000", lookup.answer("budget battery management"))
		self.assertIn(budget, lookup.answer("budget all"))
		self.assertIn("/erp part", lookup.answer("nonsense"))
		car = make_car()
		project = make_project(car.name, name=unique("BMS Master"))
		self.assertIn(project.project_name, lookup.answer(f"project {project.project_name}"))
		self.assertIn("No BOMs", lookup.answer(f"bom {unique('zzz')}"))


class TestDriveAndMonday(IntegrationTestCase):
	def tearDown(self):
		enable(drive_enabled=0, monday_enabled=0)

	def test_drive_creates_project_doc_in_its_folder(self):
		key = frappe.get_doc(
			{"doctype": "File", "file_name": "key.json", "content": b"{}", "is_private": 1}
		).insert(ignore_permissions=True)
		enable(drive_enabled=1, drive_service_account=key.file_url, drive_projects_folder="PROJECTS", drive_project_template="TEMPLATE")
		car = make_car()
		project = make_project(car.name, name="BMS Slave Board")
		fake_drive, fake_docs = MagicMock(), MagicMock()
		fake_drive.files().list().execute.return_value = {"files": []}
		fake_drive.files().create().execute.return_value = {"id": "FOLDER1"}
		fake_drive.files().copy().execute.return_value = {"id": "DOC1", "webViewLink": "https://docs.google.com/document/d/DOC1/edit"}
		with patch("ubc_solar.solar_automation.drive.services", return_value=(fake_drive, fake_docs)):
			drive.create_project_doc(project.name)
		project.reload()
		self.assertEqual((project.drive_folder_id, project.drive_doc_id), ("FOLDER1", "DOC1"))
		self.assertTrue(project.drive_doc_url.endswith("/DOC1/edit"))
		copy_kwargs = fake_drive.files().copy.call_args.kwargs
		self.assertEqual(copy_kwargs["fileId"], "TEMPLATE")
		self.assertEqual(copy_kwargs["body"]["name"], f"{car.name} BMS Slave Board Project Doc")
		update = fake_docs.documents().batchUpdate.call_args.kwargs["body"]["requests"][0]["replaceAllText"]
		self.assertEqual(update["containsText"]["text"], "{{ERP_LINK}}")
		self.assertIn(project.name, update["replaceText"])

	def test_monday_creates_item_with_link(self):
		enable(monday_enabled=1, monday_api_token="tok", monday_board_id="42", monday_link_column="link")
		car = make_car()
		project = make_project(car.name, name="Motor Controller")
		calls = []

		def fake_post(url, json=None, headers=None, timeout=None):
			calls.append(json)
			if "create_item" in json["query"]:
				return FakeResponse({"data": {"create_item": {"id": "777"}}})
			return FakeResponse({"data": {"me": {"account": {"slug": "ubcsolar"}}}})

		frappe.cache.delete_value("ubc_solar:monday_slug")
		with patch("ubc_solar.solar_automation.monday.requests.post", side_effect=fake_post):
			monday.create_project_item(project.name)
		project.reload()
		self.assertEqual(project.monday_item_id, "777")
		self.assertEqual(project.monday_item_url, "https://ubcsolar.monday.com/boards/42/pulses/777")
		variables = calls[0]["variables"]
		self.assertEqual(variables["name"], f"{car.name} Motor Controller")
		self.assertIn(project.name, json.loads(variables["values"])["link"]["url"])

	def test_disabled_integrations_do_nothing(self):
		car = make_car()
		project = make_project(car.name)
		with patch("ubc_solar.solar_automation.drive.services") as services:
			drive.create_project_doc(project.name)
		services.assert_not_called()


class TestWiki(IntegrationTestCase):
	def tearDown(self):
		enable(wiki_enabled=0)

	def test_current_car_page(self):
		frappe.db.set_value("Car", {"status": ["in", ["In Design", "Building"]]}, "status", "Active")
		car = make_car("Building")
		project = make_project(car.name, name="Pack Enclosure", subteam="Battery Mech", subsystem="Battery")
		old = make_car("Active")
		frappe.get_doc({"doctype": "Car Repair", "title": "Cracked upright", "car": old.name}).insert(ignore_permissions=True)
		md = wiki.current_car_markdown()
		self.assertIn(car.car_title, md.split("## Older cars still active")[0])
		self.assertIn("Pack Enclosure", md)
		self.assertIn("No BOM yet", md)
		self.assertIn(old.car_title, md.split("## Older cars still active")[1])
		self.assertIn("Cracked upright", md)
		self.assertIn(project.name, md)

	def test_save_page_creates_then_updates(self):
		enable(wiki_enabled=1, wiki_url="https://wiki.example.com", wiki_api_key="k")
		responses = [
			{"errors": [{"message": "This page does not exist."}]},
			{"data": {"pages": {"create": {"responseResult": {"succeeded": True}, "page": {"id": 5}}}}},
		]
		with patch("ubc_solar.solar_automation.wiki.requests.post", side_effect=[FakeResponse(r) for r in responses]) as post:
			url = wiki.save_page("current-car", "Current car", "# hi", "desc")
		self.assertEqual(url, "https://wiki.example.com/current-car")
		self.assertIn("create(", post.call_args_list[1].kwargs["json"]["query"])
		responses = [
			{"data": {"pages": {"singleByPath": {"id": 5}}}},
			{"data": {"pages": {"update": {"responseResult": {"succeeded": True}}}}},
		]
		with patch("ubc_solar.solar_automation.wiki.requests.post", side_effect=[FakeResponse(r) for r in responses]) as post:
			wiki.save_page("current-car", "Current car", "# hi", "desc")
		self.assertEqual(post.call_args_list[1].kwargs["json"]["variables"]["id"], 5)

	def test_snapshot_lists_repairs(self):
		car = make_car("Active")
		frappe.get_doc({"doctype": "Car Repair", "title": "Connector failure", "car": car.name, "status": "Fixed"}).insert(
			ignore_permissions=True
		)
		md = wiki.snapshot_markdown(car.name)
		self.assertIn("Connector failure", md)
		self.assertIn("Repair history", md)


class TestEscalation(IntegrationTestCase):
	def test_old_pending_purchase_pings_exec(self):
		from frappe.model.workflow import apply_workflow

		from ubc_solar.solar_automation.tasks import escalate_waiting_approvals

		make_budget([("Strategy", "Strategy", 100)])
		exec_ = make_member("Exec", division="Electrical")
		member = make_member("Member", subteam="Strategy")
		item = make_item("Buy", mpn=unique("GPS"))
		mr = frappe.get_doc(
			{
				"doctype": "Material Request",
				"material_request_type": "Purchase",
				"company": frappe.db.get_single_value("Solar Settings", "company"),
				"transaction_date": frappe.utils.nowdate(),
				"solar_subteam": "Strategy",
				"owner": member.user,
				"items": [{"item_code": item.name, "qty": 1, "rate": 5, "uom": "Nos", "conversion_factor": 1}],
			}
		).insert(ignore_permissions=True)
		apply_workflow(mr, "Request Approval")
		frappe.db.set_value("Material Request", mr.name, "modified", frappe.utils.add_days(frappe.utils.now_datetime(), -5), update_modified=False)
		with patch("ubc_solar.solar_automation.tasks.notify.send") as send:
			escalate_waiting_approvals()
		users = [u for call in send.call_args_list if call.args[2].name == mr.name for u in call.kwargs["users"]]
		self.assertIn(exec_.user, users)
