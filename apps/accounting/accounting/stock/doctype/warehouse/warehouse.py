# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint, nowdate
from frappe import throw, _
from frappe.utils.nestedset import NestedSet
from frappe.contacts.address_and_contact import load_address_and_contact

class Warehouse(NestedSet):
	nsm_parent_field = 'parent_warehouse'

	def autoname(self):
		self.name = self.warehouse_name

	def on_update(self):
		self.update_nsm_model()

	def update_nsm_model(self):
		frappe.utils.nestedset.update_nsm(self)

	def check_if_sle_exists(self):
		return frappe.db.sql("""select name from `tabStock Ledger Entry`
			where warehouse = %s limit 1""", self.name)

	def check_if_child_exists(self):
		return frappe.db.sql("""select name from `tabWarehouse`
			where parent_warehouse = %s limit 1""", self.name)

	def before_rename(self, old_name, new_name, merge=False):
		super(Warehouse, self).before_rename(old_name, new_name, merge)

		if merge:
			if not frappe.db.exists("Warehouse", new_warehouse):
				frappe.throw(_("Warehouse {0} does not exist").format(new_warehouse))

		return new_warehouse

	def after_rename(self, old_name, new_name, merge=False):
		super(Warehouse, self).after_rename(old_name, new_name, merge)

		self.db_set("warehouse_name", new_name)

	def convert_to_group_or_ledger(self):
		if self.is_group:
			self.convert_to_ledger()
		else:
			self.convert_to_group()

	def convert_to_ledger(self):
		if self.check_if_child_exists():
			frappe.throw(_("Warehouses with child nodes cannot be converted to ledger"))
		elif self.check_if_sle_exists():
			throw(_("Warehouses with existing transaction can not be converted to ledger."))
		else:
			self.is_group = 0
			self.save()
			return 1

	def convert_to_group(self):
		if self.check_if_sle_exists():
			throw(_("Warehouses with existing transaction can not be converted to group."))
		else:
			self.is_group = 1
			self.save()
			return 1

@frappe.whitelist()
def get_children(doctype, parent=None, company=None, is_root=False):

	if is_root:
		parent = ""

	fields = ['name as value', 'is_group as expandable']
	filters = [
		['docstatus', '<', '2'],
		['ifnull(`parent_warehouse`, "")', '=', parent]
	]

	warehouses = frappe.get_list(doctype, fields=fields, filters=filters, order_by='name')
	return warehouses

@frappe.whitelist()
def add_node():
	from frappe.desk.treeview import make_tree_args
	args = make_tree_args(**frappe.form_dict)

	if cint(args.is_root):
		args.parent_warehouse = None

	frappe.get_doc(args).insert()

@frappe.whitelist()
def convert_to_group_or_ledger():
	args = frappe.form_dict
	return frappe.get_doc("Warehouse", args.docname).convert_to_group_or_ledger()

def get_child_warehouses(warehouse):
	lft, rgt = frappe.get_cached_value("Warehouse", warehouse, [lft, rgt])

	return frappe.db.sql_list("""select name from `tabWarehouse`
		where lft >= %s and rgt <= %s""", (lft, rgt))

def get_warehouses_based_on_account(account, company=None):
	warehouses = []
	for d in frappe.get_all("Warehouse", fields = ["name", "is_group"],
		filters = {"account": account}):
		if d.is_group:
			warehouses.extend(get_child_warehouses(d.name))
		else:
			warehouses.append(d.name)

	if not warehouses:
		frappe.throw(_("Warehouse not found against the account {0}")
			.format(account))

	return warehouses
