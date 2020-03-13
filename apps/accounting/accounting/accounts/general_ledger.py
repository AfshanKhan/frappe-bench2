# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe, accounting
from frappe.utils import flt, cstr, cint, comma_and
from frappe import _
from frappe.model.meta import get_field_precision

def make_gl_entries(gl_map, cancel=False, adv_adj=False, merge_entries=True, update_outstanding='Yes', from_repost=False):
	if gl_map:
		gl_map = process_gl_map(gl_map, merge_entries)
		if gl_map and len(gl_map) > 1:
			save_entries(gl_map, adv_adj, update_outstanding, from_repost)
		else:
			frappe.throw(_("Incorrect number of General Ledger Entries found. You might have selected a wrong Account in the transaction."))
		
def process_gl_map(gl_map, merge_entries=True):
	if merge_entries:
		gl_map = merge_similar_entries(gl_map)
	for entry in gl_map:
		# toggle debit, credit if negative entry
		if flt(entry.debit) < 0:
			entry.credit = flt(entry.credit) - flt(entry.debit)
			entry.debit = 0.0

		if flt(entry.credit) < 0:
			entry.debit = flt(entry.debit) - flt(entry.credit)
			entry.credit = 0.0

	return gl_map

def merge_similar_entries(gl_map):
	merged_gl_map = []
	for entry in gl_map:
		# if there is already an entry in this account then just add it
		# to that entry
		same_head = check_if_in_list(entry, merged_gl_map)
		if same_head:
			same_head.debit	= flt(same_head.debit) + flt(entry.debit)
			same_head.credit = flt(same_head.credit) + flt(entry.credit)
		else:
			merged_gl_map.append(entry)

	precision = get_field_precision(frappe.get_meta("GL Entry").get_field("debit"), "INR")

	# filter zero debit and credit entries
	merged_gl_map = filter(lambda x: flt(x.debit, precision)!=0 or flt(x.credit, precision)!=0, merged_gl_map)
	merged_gl_map = list(merged_gl_map)

	return merged_gl_map

def check_if_in_list(gle, gl_map):
	account_head_fieldnames = ['party_type', 'party', 'against_voucher', 'against_voucher_type']

	for e in gl_map:
		same_head = True
		if e.account != gle.account:
			same_head = False

		for fieldname in account_head_fieldnames:
			if cstr(e.get(fieldname)) != cstr(gle.get(fieldname)):
				same_head = False

		if same_head:
			return e

def save_entries(gl_map, adv_adj, update_outstanding, from_repost=False):
	for entry in gl_map:
		make_entry(entry, adv_adj, update_outstanding, from_repost)

def make_entry(args, adv_adj, update_outstanding, from_repost=False):
	args.update({"doctype": "GL Entry"})
	gle = frappe.get_doc(args)
	gle.flags.ignore_permissions = 1
	gle.flags.from_repost = from_repost
	gle.validate()
	gle.flags.ignore_permissions = True
	gle.db_insert()
	gle.run_method("on_update_with_args", adv_adj, update_outstanding, from_repost)
	gle.flags.ignore_validate = True
	gle.submit()
