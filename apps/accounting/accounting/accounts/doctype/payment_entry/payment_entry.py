# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, accounting, json
from frappe import _, scrub, ValidationError
from frappe.utils import flt, comma_or, nowdate, getdate
from accounting.accounts.doctype.journal_entry.journal_entry import get_party_account, get_gl_dict
from accounting.accounts.general_ledger import make_gl_entries
from frappe.model.document import Document

from six import string_types, iteritems

class InvalidPaymentEntry(ValidationError):
	pass


class PaymentEntry(Document):
	def __init__(self, *args, **kwargs):
		super(PaymentEntry, self).__init__(*args, **kwargs)
		if not self.is_new():
			self.setup_party_account_field()

	def setup_party_account_field(self):
		self.party_account_field = None
		self.party_account = None

		if self.payment_type == "Receive":
			self.party_account_field = "paid_from"
			self.party_account = self.paid_from
			
		elif self.payment_type == "Pay":
			self.party_account_field = "paid_to"
			self.party_account = self.paid_to
			
	def validate(self):
		self.setup_party_account_field()
		self.set_missing_values()
		self.validate_payment_type()
		self.set_title()
		self.set_remarks()
		self.set_status()

	def on_submit(self):
		self.setup_party_account_field()
		self.make_gl_entries()
		self.set_status()


	def on_cancel(self):
		self.setup_party_account_field()
		self.make_gl_entries(cancel=1)
		self.set_status()
	
	def set_missing_values(self):
		if not self.party_type:
			frappe.throw(_("Party Type is mandatory"))

		if not self.party:
			frappe.throw(_("Party is mandatory"))

		_party_name = self.party_type.lower() + "_name"
		self.party_name = frappe.db.get_value(self.party_type, self.party, _party_name)

			
		if not self.party_account:
			party_account = get_party_account(self.party_type, self.party, self.company)
			self.set(self.party_account_field, party_account)
			self.party_account = party_account

	def validate_payment_type(self):
		if self.payment_type not in ("Receive", "Pay"):
			frappe.throw(_("Payment Type must be one of Receive or Pay"))
	
	def set_status(self):
		if self.docstatus == 2:
			self.status = 'Cancelled'
		elif self.docstatus == 1:
			self.status = 'Submitted'
		else:
			self.status = 'Draft'

	def set_title(self):
		if self.payment_type in ("Receive", "Pay"):
			self.title = self.party
		else:
			self.title = self.paid_from + " - " + self.paid_to

	def set_remarks(self):
		if self.remarks: return

		remarks = [_("Amount {0} {1} {2}").format(
				self.paid_amount if self.payment_type=="Receive" else self.received_amount,
				_("received from") if self.payment_type=="Receive" else _("to"), self.party
			)]
		self.set("remarks", "\n".join(remarks))

	def make_gl_entries(self, cancel=0, adv_adj=0):
		if self.payment_type in ("Receive", "Pay") and not self.get("party_account_field"):
			self.setup_party_account_field()

		gl_entries = []
		self.add_party_gl_entries(gl_entries)
		self.add_gl_entries(gl_entries)
		
		make_gl_entries(gl_entries, cancel=cancel, adv_adj=adv_adj)

	def add_party_gl_entries(self, gl_entries):
		if self.party_account:
			if self.payment_type=="Receive":
				against_account = self.paid_to
				amount = self.received_amount
			else:
				against_account = self.paid_from
				amount = self.paid_amount

			party_gl_dict = get_gl_dict(self, args={
				"account": self.party_account,
				"party_type": self.party_type,
				"party": self.party,
				"against": against_account,
			})
			account_type = frappe.db.get_value("Account", self.party_account, "account_type")
			dr_or_cr = "credit" if account_type == 'Receivable' else "debit"
			print(dr_or_cr)

			gle = party_gl_dict.copy()

			gle.update({
				dr_or_cr: amount
			})

			gl_entries.append(gle)

	def add_gl_entries(self, gl_entries):
		if self.payment_type in ("Pay"):
			gl_entries.append(
				get_gl_dict(self, args={
					"account": self.paid_from,
					"against": self.party,
					"credit": self.paid_amount,
				})
			)
		if self.payment_type in ("Receive"):
			gl_entries.append(
				get_gl_dict(self, args={
					"account": self.paid_to,
					"against": self.party,
					"debit": self.received_amount,
				})
			)

@frappe.whitelist()
def get_party_details(company, party_type, party, date, cost_center=None):
	if not frappe.db.exists(party_type, party):
		frappe.throw(_("Invalid {0}: {1}").format(party_type, party))

	party_account = get_party_account(party_type, party, company)

	_party_name = party_type.lower() + "_name"
	party_name = frappe.db.get_value(party_type, party, _party_name)
	print(party_name)
	print(party_account)
	
	return {
		"party_account": party_account,
		"party_name": party_name,
		}