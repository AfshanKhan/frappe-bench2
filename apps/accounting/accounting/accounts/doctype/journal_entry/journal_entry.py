# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe.model.document import Document
import frappe, accounting, json
from frappe.utils import cstr, flt, fmt_money, formatdate, getdate, nowdate, cint, get_link_to_form
from frappe import msgprint, _, scrub

from six import string_types, iteritems

class FiscalYearError(frappe.ValidationError): pass

class JournalEntry(Document):
	def __init__(self, *args, **kwargs):
		super(JournalEntry, self).__init__(*args, **kwargs)

	def get_feed(self):
		return self.voucher_type

	def validate(self):
		if not self.is_opening:
			self.is_opening='No'
		self.clearance_date = None

		self.validate_party()
		self.set_amounts()
		self.validate_total_debit_and_credit()
		self.validate_against_jv()
		self.set_against_account()
		self.create_remarks()
		self.validate_empty_accounts_table()
		self.set_account_and_party_balance()
		if not self.title:
			self.title = self.get_title()

	def on_submit(self):
		self.make_gl_entries()

	def on_cancel(self):
		self.make_gl_entries(1)
		
	def get_title(self):
		pay_to_recd_from = None
		for d in self.get('accounts'):
			if d.party_type in ['Customer', 'Supplier'] and d.party:
				if not pay_to_recd_from:
					pay_to_recd_from = frappe.db.get_value(d.party_type, d.party,
						"customer_name" if d.party_type=="Customer" else "supplier_name")

		if pay_to_recd_from:
			self.pay_to_recd_from = pay_to_recd_from
		
			return self.pay_to_recd_from 
		else:
			return self.accounts[0].account

	def validate_party(self):
		for d in self.get("accounts"):
			account_type = frappe.db.get_value("Account", d.account, "account_type")
			if account_type in ["Receivable", "Payable"]:
				if not (d.party_type and d.party):
					frappe.throw(_("Row {0}: Party Type and Party is required for Receivable / Payable account {1}").format(d.idx, d.account))

	def validate_against_jv(self):
		for d in self.get('accounts'):
			if d.reference_type=="Journal Entry":
				account_root_type = frappe.db.get_value("Account", d.account, "root_type")
				if account_root_type == "Asset" and flt(d.debit) > 0:
					frappe.throw(_("For {0}, only credit accounts can be linked against another debit entry")
						.format(d.account))
				elif account_root_type == "Liability" and flt(d.credit) > 0:
					frappe.throw(_("For {0}, only debit accounts can be linked against another credit entry")
						.format(d.account))

				if d.reference_name == self.name:
					frappe.throw(_("You can not enter current voucher in 'Against Journal Entry' column"))

				against_entries = frappe.db.sql("""select * from `tabJournal Entry Account`
					where account = %s and docstatus = 1 and parent = %s
					and (reference_type is null or reference_type in ("", "Sales Order", "Purchase Order"))
					""", (d.account, d.reference_name), as_dict=True)

				if not against_entries:
					frappe.throw(_("Journal Entry {0} does not have account {1} or already matched against other voucher")
						.format(d.reference_name, d.account))
				else:
					dr_or_cr = "debit" if d.credit > 0 else "credit"
					valid = False
					for jvd in against_entries:
						if flt(jvd[dr_or_cr]) > 0:
							valid = True
					if not valid:
						frappe.throw(_("Against Journal Entry {0} does not have any unmatched {1} entry")
							.format(d.reference_name, dr_or_cr))

	def set_against_account(self):
		accounts_debited, accounts_credited = [], []
		for d in self.get("accounts"):
			if flt(d.debit > 0): accounts_debited.append(d.party or d.account)
			if flt(d.credit) > 0: accounts_credited.append(d.party or d.account)

		for d in self.get("accounts"):
			if flt(d.debit > 0): d.against_account = ", ".join(list(set(accounts_credited)))
			if flt(d.credit > 0): d.against_account = ", ".join(list(set(accounts_debited)))

	def validate_total_debit_and_credit(self):
		self.set_total_debit_credit()
		if self.difference:
			frappe.throw(_("Total Debit must be equal to Total Credit. The difference is {0}")
				.format(self.difference))

	def set_total_debit_credit(self):
		self.total_debit, self.total_credit, self.difference = 0, 0, 0
		for d in self.get("accounts"):
			if d.debit and d.credit:
				frappe.throw(_("You cannot credit and debit same account at the same time"))

			self.total_debit = flt(self.total_debit) + flt(d.debit, d.precision("debit"))
			self.total_credit = flt(self.total_credit) + flt(d.credit, d.precision("credit"))

		self.difference = flt(self.total_debit, self.precision("total_debit")) - \
			flt(self.total_credit, self.precision("total_credit"))

	def set_amounts(self):
		for d in self.get("accounts"):
			d.debit = flt(d.debit, d.precision("debit"))
			d.credit = flt(d.credit, d.precision("credit"))

	def create_remarks(self):
		r = []

		if self.user_remark:
			r.append(_("Note: {0}").format(self.user_remark))

		for d in self.get('accounts'):
			if d.reference_type=="Sales Invoice" and d.credit:
				r.append(_("{0} against Sales Invoice {1}").format(fmt_money(flt(d.credit), currency = self.company_currency), \
					d.reference_name))

			if d.reference_type == "Purchase Invoice" and d.debit:
				bill_no = frappe.db.sql("""select bill_no, bill_date
					from `tabPurchase Invoice` where name=%s""", d.reference_name)
				if bill_no and bill_no[0][0] and bill_no[0][0].lower().strip() \
						not in ['na', 'not applicable', 'none']:
					r.append(_('{0} against Bill {1} dated {2}').format(fmt_money(flt(d.debit), currency=self.company_currency), bill_no[0][0],
						bill_no[0][1] and formatdate(bill_no[0][1].strftime('%Y-%m-%d'))))

		if r:
			self.remark = ("\n").join(r) #User Remarks is not mandatory

	def make_gl_entries(self, cancel=0, adv_adj=0):
		from accounting.accounts.general_ledger import make_gl_entries

		gl_map = []
		for d in self.get("accounts"):
			if d.debit or d.credit:
				r = [d.user_remark, self.remark]
				r = [x for x in r if x]
				remarks = "\n".join(r)

				gl_map.append(
					get_gl_dict({
						"account": d.account,
						"party_type": d.party_type,
						"party": d.party,
						"against": d.against_account,
						"debit": flt(d.debit, d.precision("debit")),
						"credit": flt(d.credit, d.precision("credit")),
						"remarks": remarks,
					}, item=d)
				)

		if gl_map:
			make_gl_entries(gl_map, cancel=cancel, adv_adj=adv_adj)

	
	def get_balance(self):
		if not self.get('accounts'):
			msgprint(_("'Entries' cannot be empty"), raise_exception=True)
		else:
			self.total_debit, self.total_credit = 0, 0
			diff = flt(self.difference, self.precision("difference"))

			# If any row without amount, set the diff on that row
			if diff:
				blank_row = None
				for d in self.get('accounts'):
					if not d.credit and not d.debit and diff != 0:
						blank_row = d

				if not blank_row:
					blank_row = self.append('accounts', {})

				blank_row.exchange_rate = 1
				if diff>0:
					blank_row.credit = diff
				elif diff<0:
					blank_row.debit = abs(diff)

			self.validate_total_debit_and_credit()

		jd2 = self.append('accounts', {})
		if self.write_off_based_on == 'Accounts Receivable':
			jd2.debit = total
		elif self.write_off_based_on == 'Accounts Payable':
			jd2.credit = total

		self.validate_total_debit_and_credit()

	def validate_empty_accounts_table(self):
		if not self.get('accounts'):
			frappe.throw(_("Accounts table cannot be blank."))

	def set_account_and_party_balance(self):
		account_balance = {}
		party_balance = {}
		for d in self.get("accounts"):
			if d.account not in account_balance:
				account_balance[d.account] = get_balance_on(account=d.account, date=self.posting_date)

			if (d.party_type, d.party) not in party_balance:
				party_balance[(d.party_type, d.party)] = get_balance_on(party_type=d.party_type,
					party=d.party, date=self.posting_date, company=self.company)

			d.account_balance = account_balance[d.account]
			d.party_balance = party_balance[(d.party_type, d.party)]

@frappe.whitelist()
def get_default_cash_account(company, account_type=None, mode_of_payment=None, account=None):
	account = None
	if not account:
		'''
			Set the default account first. If the user hasn't set any default account then, he doesn't
			want us to set any random account. In this case set the account only if there is single
			account (of that type), otherwise return empty dict.
		'''
		if account_type=="Cash":
			account = frappe.get_cached_value('Company',  company,  "default_cash_account")
			if not account:
				account_list = frappe.get_all("Account", filters = {"company": company,
					"account_type": "Cash", "is_group": 0})
				if len(account_list) == 1:
					account = account_list[0].name

	if account:
		account_details = frappe.db.get_value("Account", account,
			["account_type"], as_dict=1)

		return frappe._dict({
			"account": account,
			"balance": get_balance_on(account),
			"account_type": account_details.account_type
		})
	else: return frappe._dict()

def get_balance_on(account=None, date=None, party_type=None, party=None, company=None, ignore_account_permission=False):
	if not account and frappe.form_dict.get("account"):
		account = frappe.form_dict.get("account")
	if not date and frappe.form_dict.get("date"):
		date = frappe.form_dict.get("date")
	if not party_type and frappe.form_dict.get("party_type"):
		party_type = frappe.form_dict.get("party_type")
	if not party and frappe.form_dict.get("party"):
		party = frappe.form_dict.get("party")

	cond = []
	if date:
		cond.append("posting_date <= %s" % frappe.db.escape(cstr(date)))
	else:
		# get balance of all entries that exist
		date = nowdate()

	if account:
		acc = frappe.get_doc("Account", account)

	try:
		year_start_date = get_fiscal_year(date, verbose=0)[0]
	except FiscalYearError:
		if getdate(date) > getdate(nowdate()):
			# if fiscal year not found and the date is greater than today
			# get fiscal year for today's date and its corresponding year start date
			year_start_date = get_fiscal_year(nowdate(), verbose=1)[0]
		else:
			# this indicates that it is a date older than any existing fiscal year.
			# hence, assuming balance as 0.0
			return 0.0

	if account:
		report_type = acc.report_type
	else:
		report_type = ""

	if account:

		if not (frappe.flags.ignore_account_permission
			or ignore_account_permission):
			acc.check_permission("read")

		if report_type == 'Profit and Loss':
			# for pl accounts, get balance within a fiscal year
			cond.append("posting_date >= '%s' and voucher_type != 'Period Closing Voucher'" \
				% year_start_date)
		# different filter for group and ledger - improved performance
		if acc.is_group:
			cond.append("""exists (
				select name from `tabAccount` ac where ac.name = gle.account
				and ac.lft >= %s and ac.rgt <= %s
			)""" % (acc.lft, acc.rgt))

		else:
			cond.append("""gle.account = %s """ % (frappe.db.escape(account, percent=False), ))

	if party_type and party:
		cond.append("""gle.party_type = %s and gle.party = %s """ %
			(frappe.db.escape(party_type), frappe.db.escape(party, percent=False)))

	if company:
		cond.append("""gle.company = %s """ % (frappe.db.escape(company, percent=False)))

	if account or (party_type and party):
		
		select_field = "sum(debit) - sum(credit)"
		bal = frappe.db.sql("""
			SELECT {0}
			FROM `tabGL Entry` gle
			WHERE {1}""".format(select_field, " and ".join(cond)))[0][0]

		# if bal is None, return 0
		return flt(bal)

def get_fiscal_year(transaction_date=None, fiscal_year=None, label="Date", verbose=1, company=None, as_dict=False):
	fiscal_years = frappe.cache().hget("fiscal_years", company) or []
	if not fiscal_years:
		# if year start date is 2012-04-01, year end date should be 2013-03-31 (hence subdate)
		cond = ""
		if fiscal_year:
			cond += " and fy.name = {0}".format(frappe.db.escape(fiscal_year))
		if company:
			cond += """
				and (not exists (select name
					from `tabFiscal Year Company` fyc
					where fyc.parent = fy.name)
				or exists(select company
					from `tabFiscal Year Company` fyc
					where fyc.parent = fy.name
					and fyc.company=%(company)s)
				)
			"""

		fiscal_years = frappe.db.sql("""
			select
				fy.name, fy.year_start_date, fy.year_end_date
			from
				`tabFiscal Year` fy
			where
				disabled = 0 {0}
			order by
				fy.year_start_date desc""".format(cond), {
				"company": company
			}, as_dict=True)
		frappe.cache().hset("fiscal_years", company, fiscal_years)

	if transaction_date:
		transaction_date = getdate(transaction_date)
		
	for fy in fiscal_years:
		matched = False
		if fiscal_year and fy.name == fiscal_year:
			matched = True
			
		if (transaction_date and getdate(fy.year_start_date) <= transaction_date
			and getdate(fy.year_end_date) >= transaction_date):
			matched = True
			
		if matched:
			if as_dict:
				return (fy,)
			else:
				return ((fy.name, fy.year_start_date, fy.year_end_date),)
	
	error_msg = _("""{0} {1} not in any active Fiscal Year.""").format(label, formatdate(transaction_date))
	if verbose==1: frappe.msgprint(error_msg)
	raise FiscalYearError(error_msg)

@frappe.whitelist()
def get_opening_accounts(company):
	"""get all balance sheet accounts for opening entry"""
	accounts = frappe.db.sql_list("""select
			name from tabAccount
		where
			is_group=0 and report_type='Balance Sheet' and company={0} and
			name not in (select distinct account from tabWarehouse where
			account is not null and account != '')
		order by name asc""".format(frappe.db.escape(company)))

	return [{"account": a, "balance": get_balance_on(a)} for a in accounts]


def get_against_jv(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select jv.name, jv.posting_date, jv.user_remark
		from `tabJournal Entry` jv, `tabJournal Entry Account` jv_detail
		where jv_detail.parent = jv.name and jv_detail.account = %s and ifnull(jv_detail.party, '') = %s
		and (jv_detail.reference_type is null or jv_detail.reference_type = '')
		and jv.docstatus = 1 and jv.`{0}` like %s order by jv.name desc limit %s, %s""".format(searchfield),
		(filters.get("account"), cstr(filters.get("party")), "%{0}%".format(txt), start, page_len))

@frappe.whitelist()
def get_party_account_and_balance(company, party_type, party, cost_center=None):
	if not frappe.has_permission("Account"):
		frappe.msgprint(_("No Permission"), raise_exception=1)

	account = get_party_account(party_type, party, company)

	account_balance = get_balance_on(account=account)
	party_balance = get_balance_on(party_type=party_type, party=party, company=company)

	return {
		"account": account,
		"balance": account_balance,
		"party_balance": party_balance,
	}

def get_party_account(party_type, party, company):
	"""Returns the account for the given `party`.
		Will first search in party (Customer / Supplier) record, if not found,
		will search in group (Customer Group / Supplier Group),
		finally will return default."""
	if not company:
		frappe.throw(_("Please select a Company"))

	if not party:
		return

	account = frappe.db.get_value("Party Account",
		{"parenttype": party_type, "parent": party, "company": company}, "account")

	if not account and party_type in ['Customer', 'Supplier']:
		party_group_doctype = "Supplier Group" if party_type=="Supplier" else None
		group = frappe.get_cached_value(party_type, party, scrub(party_group_doctype))
		account = frappe.db.get_value("Party Account",
			{"parenttype": party_group_doctype, "parent": group, "company": company}, "account")

	if not account and party_type in ['Customer', 'Supplier']:
		default_account_name = "default_receivable_account" \
			if party_type=="Customer" else "default_payable_account"
		account = frappe.get_cached_value('Company',  company,  default_account_name)

	return account

@frappe.whitelist()
def get_account_balance_and_party_type(account, date, company, debit=None, credit=None, exchange_rate=None, cost_center=None):
	"""Returns dict of account balance and party type to be set in Journal Entry on selection of account."""
	if not frappe.has_permission("Account"):
		frappe.msgprint(_("No Permission"), raise_exception=1)

	account_details = frappe.db.get_value("Account", account, ["account_type"], as_dict=1)

	if not account_details:
		return

	if account_details.account_type == "Receivable":
		party_type = "Customer"
	elif account_details.account_type == "Payable":
		party_type = "Supplier"
	else:
		party_type = ""

	grid_values = {
		"balance": get_balance_on(account, date),
		"party_type": party_type,
		"account_type": account_details.account_type
	}

	# un-set party if not party type
	if not party_type:
		grid_values["party"] = ""

	return grid_values

def get_gl_dict(self, args, account_currency=None, item=None):
		"""this method populates the common properties of a gl entry record"""
		# company = frappe.db.get_value("Company", "Gada Electronics",['name'], as_dict=False)
		posting_date = args.get('posting_date') or self.get('posting_date')
		fiscal_years = get_fiscal_year(posting_date, company=self.get('company'))
		if len(fiscal_years) > 1:
			frappe.throw(_("Multiple fiscal years exist for the date {0}. Please set company in Fiscal Year").format(
				formatdate(posting_date)))
		else:
			fiscal_year = fiscal_years[0][0]

		gl_dict = frappe._dict({
			'company': self.get('company'),
			'posting_date': posting_date,
			'fiscal_year': fiscal_year,
			'voucher_type': self.get('doctype'),
			'voucher_no': self.get('name'),
			'remarks': self.get("remarks"),
			'debit': 0,
			'credit': 0,
			'is_opening': self.get("is_opening") or "No",
			'party_type': None,
			'party': None,
		})
		gl_dict.update(args)

		return gl_dict
