# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _, msgprint, throw
import frappe.defaults
from frappe.utils import flt, cint, cstr, today
from frappe.desk.reportview import build_match_conditions, get_filters_cond
from frappe.contacts.address_and_contact import load_address_and_contact, delete_contact_and_address
from frappe.model.rename_doc import update_linked_doctypes
from frappe.model.mapper import get_mapped_doc

class Customer(Document):
	def get_feed(self):
		return self.customer_name

	def onload(self):
		"""Load address and contacts in `__onload`"""
		load_address_and_contact(self)
		
	def get_customer_name(self):
		if frappe.db.get_value("Customer", self.customer_name):
			count = frappe.db.sql("""select ifnull(MAX(CAST(SUBSTRING_INDEX(name, ' ', -1) AS UNSIGNED)), 0) from tabCustomer
				 where name like %s""", "%{0} - %".format(self.customer_name), as_list=1)[0][0]
			count = cint(count) + 1
			return "{0} - {1}".format(self.customer_name, cstr(count))

		return self.customer_name

	def validate(self):
		self.flags.is_new_doc = self.is_new()
		
	def on_update(self):
		self.create_primary_contact()
		self.create_primary_address()
	
	def create_primary_contact(self):
		if not self.customer_primary_contact:
			if self.mobile_no or self.email_id:
				contact = make_contact(self)
				self.db_set('customer_primary_contact', contact.name)
				self.db_set('mobile_no', self.mobile_no)
				self.db_set('email_id', self.email_id)

	def create_primary_address(self):
		if self.flags.is_new_doc and self.get('address_line1'):
			make_address(self)

	def on_trash(self):
		if self.customer_primary_contact:
			frappe.db.sql("""update `tabCustomer`
				set customer_primary_contact=null, mobile_no=null, email_id=null
				where name=%s""", self.name)

		delete_contact_and_address('Customer', self.name)
		
	def after_rename(self, olddn, newdn, merge=False):
		if frappe.defaults.get_global_default('cust_master_name') == 'Customer Name':
			frappe.db.set(self, "customer_name", newdn)

def create_contact(contact, party_type, party, email):
	"""Create contact based on given contact name"""
	contact = contact.split(' ')

	contact = frappe.get_doc({
		'doctype': 'Contact',
		'first_name': contact[0],
		'last_name': len(contact) > 1 and contact[1] or ""
	})
	contact.append('email_ids', dict(email_id=email, is_primary=1))
	contact.append('links', dict(link_doctype=party_type, link_name=party))
	contact.insert()

def _set_missing_values(source, target):
	address = frappe.get_all('Dynamic Link', {
			'link_doctype': source.doctype,
			'link_name': source.name,
			'parenttype': 'Address',
		}, ['parent'], limit=1)

	contact = frappe.get_all('Dynamic Link', {
			'link_doctype': source.doctype,
			'link_name': source.name,
			'parenttype': 'Contact',
		}, ['parent'], limit=1)

	if address:
		target.customer_address = address[0].parent

	if contact:
		target.contact_person = contact[0].parent


def get_customer_list(doctype, txt, searchfield, start, page_len, filters=None):
	if frappe.db.get_default("cust_master_name") == "Customer Name":
		fields = ["name"]
	else:
		fields = ["name", "customer_name"]

	match_conditions = build_match_conditions("Customer")
	match_conditions = "and {}".format(match_conditions) if match_conditions else ""

	if filters:
		filter_conditions = get_filters_cond(doctype, filters, [])
		match_conditions += "{}".format(filter_conditions)

	return frappe.db.sql("""select %s from `tabCustomer` where docstatus < 2
		and (%s like %s or customer_name like %s)
		{match_conditions}
		order by
		case when name like %s then 0 else 1 end,
		case when customer_name like %s then 0 else 1 end,
		name, customer_name limit %s, %s""".format(match_conditions=match_conditions) %
		(", ".join(fields), searchfield, "%s", "%s", "%s", "%s", "%s", "%s"),
		("%%%s%%" % txt, "%%%s%%" % txt, "%%%s%%" % txt, "%%%s%%" % txt, start, page_len))

def make_contact(args, is_primary_contact=1):
	contact = frappe.get_doc({
		'doctype': 'Contact',
		'first_name': args.get('name'),
		'is_primary_contact': is_primary_contact,
		'links': [{
			'link_doctype': args.get('doctype'),
			'link_name': args.get('name')
		}]
	})
	if args.get('email_id'):
		contact.add_email(args.get('email_id'), is_primary=True)
	if args.get('mobile_no'):
		contact.add_phone(args.get('mobile_no'), is_primary_mobile_no=True)
	contact.insert()

	return contact

def make_address(args, is_primary_address=1):
	reqd_fields = []
	for field in ['city', 'country']:
		if not args.get(field):
			reqd_fields.append( '<li>' + field.title() + '</li>')

	if reqd_fields:
		msg = _("Following fields are mandatory to create address:")
		frappe.throw("{0} <br><br> <ul>{1}</ul>".format(msg, '\n'.join(reqd_fields)),
			title = _("Missing Values Required"))

	address = frappe.get_doc({
		'doctype': 'Address',
		'address_title': args.get('name'),
		'address_line1': args.get('address_line1'),
		'address_line2': args.get('address_line2'),
		'city': args.get('city'),
		'state': args.get('state'),
		'pincode': args.get('pincode'),
		'country': args.get('country'),
		'links': [{
			'link_doctype': args.get('doctype'),
			'link_name': args.get('name')
		}]
	}).insert()

	return address

def get_customer_primary_contact(doctype, txt, searchfield, start, page_len, filters):
	customer = filters.get('customer')
	return frappe.db.sql("""
		select `tabContact`.name from `tabContact`, `tabDynamic Link`
			where `tabContact`.name = `tabDynamic Link`.parent and `tabDynamic Link`.link_name = %(customer)s
			and `tabDynamic Link`.link_doctype = 'Customer'
			and `tabContact`.name like %(txt)s
		""", {
			'customer': customer,
			'txt': '%%%s%%' % txt
		})
