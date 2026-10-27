"""Role Profile, applied to its users straight away.

Frappe queues re-applying an edited profile as a background job and locks the
profile until that job runs, so a second edit (or one made while workers are down)
fails with "document is locked". The team is small enough to do it immediately.
Re-applying also doesn't need the editor to have rights on User, so Captain and
Execs can edit profiles (within the roles they have; see
team_member.check_role_profile_change).
"""

import frappe
from frappe.core.doctype.role_profile.role_profile import RoleProfile


class SolarRoleProfile(RoleProfile):
	def on_update(self):
		self.clear_cache()
		self.update_all_users()

	def update_all_users(self):
		for name in set(frappe.get_all("User Role Profile", filters={"role_profile": self.name, "parenttype": "User"}, pluck="parent")):
			if name in ("Administrator", "Guest"):
				continue
			user = frappe.get_doc("User", name)
			user.flags.ignore_permissions = True
			user.save()
