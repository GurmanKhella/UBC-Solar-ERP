# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

from frappe.contacts.address_and_contact import load_address_and_contact
from frappe.model.document import Document


class Sponsor(Document):
	def onload(self):
		load_address_and_contact(self)

	def validate(self):
		self.sponsor_name = (self.sponsor_name or "").strip()
		self.interactions = sorted(self.interactions, key=lambda r: str(r.date or ""), reverse=True)
		for idx, row in enumerate(self.interactions, start=1):
			row.idx = idx
