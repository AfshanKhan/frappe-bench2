// Copyright (c) 2020, Frappe and contributors
// For license information, please see license.txt

frappe.provide("accounting.accounts");
frappe.provide("accounting.journal_entry");


frappe.ui.form.on("Journal Entry", {

	refresh: function(frm) {
		frm.cscript.voucher_type(frm.doc);

		if(frm.doc.docstatus==1) {
			frm.add_custom_button(__('Ledger'), function() {
				frappe.route_options = {
					"voucher_no": frm.doc.name,
					"from_date": frm.doc.posting_date,
					"to_date": frm.doc.posting_date,
					"company": frm.doc.company,
					"group_by_voucher": 0
				};
				frappe.set_route("query-report", "General Ledger");
			}, __('View'));
		}

		if(frm.doc.docstatus==1) {
			frm.add_custom_button(__('Reverse Journal Entry'), function() {
				return accounting.journal_entry.reverse_journal_entry(frm);
			}, __('Make'));
		}

		if (frm.doc.__islocal) {
			frm.add_custom_button(__('Quick Entry'), function() {
				return accounting.journal_entry.quick_entry(frm);
			});
		}

	},
});

accounting.accounts.JournalEntry = frappe.ui.form.Controller.extend({
	onload: function() {
		this.load_defaults();
		this.setup_queries();
		this.setup_balance_formatter();
	},

	onload_post_render: function() {
		cur_frm.get_field("accounts").grid.set_multiple_add("account");
	},

	load_defaults: function() {
		//this.frm.show_print_first = true;
		if(this.frm.doc.__islocal && this.frm.doc.company) {
			frappe.model.set_default_values(this.frm.doc);
			$.each(this.frm.doc.accounts || [], function(i, jvd) {
				frappe.model.set_default_values(jvd);
			});
			var posting_date = this.frm.posting_date;
			if(!this.frm.doc.amended_from) this.frm.set_value('posting_date', posting_date || frappe.datetime.get_today());
		}
	},

	setup_queries: function() {
		var me = this;

		me.frm.set_query("account", "accounts", function(doc, cdt, cdn) {
			return accounting.journal_entry.account_query(me.frm);
		});

		me.frm.set_query("party_type", "accounts", function(doc, cdt, cdn) {
			const row = locals[cdt][cdn];

			return {
				query: "accounting.setup.doctype.party_type.party_type.get_party_type",
				filters: {
					'account': row.account
				}
			}
		});

		me.frm.set_query("reference_name", "accounts", function(doc, cdt, cdn) {
			var jvd = frappe.get_doc(cdt, cdn);

			// journal entry
			if(jvd.reference_type==="Journal Entry") {
				frappe.model.validate_missing(jvd, "account");
				return {
					query: "accounting.accounts.doctype.journal_entry.journal_entry.get_against_jv",
					filters: {
						account: jvd.account,
						party: jvd.party
					}
				};
			}

			var out = {
				filters: [
					[jvd.reference_type, "docstatus", "=", 1]
				]
			};

			if(in_list(["Sales Invoice", "Purchase Invoice"], jvd.reference_type)) {
				frappe.model.validate_missing(jvd, "account");
				var party_account_field = jvd.reference_type==="Sales Invoice" ? "debit_to": "credit_to";
				out.filters.push([jvd.reference_type, party_account_field, "=", jvd.account]);
			}

			if(jvd.party_type && jvd.party) {
				var party_field = "";
				if(jvd.reference_type.indexOf("Sales")===0) {
					var party_field = "customer";
				} else if (jvd.reference_type.indexOf("Purchase")===0) {
					var party_field = "supplier";
				}

				if (party_field) {
					out.filters.push([jvd.reference_type, party_field, "=", jvd.party]);
				}
			}

			return out;
		});


	},

	setup_balance_formatter: function() {
		var me = this;
		$.each(["balance", "party_balance"], function(i, field) {
			var df = frappe.meta.get_docfield("Journal Entry Account", field, me.frm.doc.name);
			df.formatter = function(value, df, options, doc) {
				var currency = frappe.meta.get_field_currency(df, doc);
				var dr_or_cr = value ? ('<label>' + (value > 0.0 ? __("Dr") : __("Cr")) + '</label>') : "";
				return "<div style='text-align: right'>"
					+ ((value==null || value==="") ? "" : format_currency(Math.abs(value), currency))
					+ " " + dr_or_cr
					+ "</div>";
			}
		})
	},

	accounts_add: function(doc, cdt, cdn) {
		var row = frappe.get_doc(cdt, cdn);
		$.each(doc.accounts, function(i, d) {
			if(d.account && d.party && d.party_type) {
				row.account = d.account;
				row.party = d.party;
				row.party_type = d.party_type;
			}
		});

		// set difference
		if(doc.difference) {
			if(doc.difference > 0) {
				row.credit = doc.difference;
			} else {
				row.debit = -doc.difference;
			}
		}
		cur_frm.cscript.update_totals(doc);
	},

});

cur_frm.script_manager.make(accounting.accounts.JournalEntry);

cur_frm.cscript.update_totals = function(doc) {
	var td=0.0; var tc =0.0;
	var accounts = doc.accounts || [];
	for(var i in accounts) {
		td += flt(accounts[i].debit, precision("debit", accounts[i]));
		tc += flt(accounts[i].credit, precision("credit", accounts[i]));
	}
	var doc = locals[doc.doctype][doc.name];
	doc.total_debit = td;
	doc.total_credit = tc;
	doc.difference = flt((td - tc), precision("difference"));
	refresh_many(['total_debit','total_credit','difference']);
}

cur_frm.cscript.get_balance = function(doc,dt,dn) {
	cur_frm.cscript.update_totals(doc);
	cur_frm.call('get_balance', null, () => { cur_frm.refresh(); });
}

cur_frm.cscript.validate = function(doc,cdt,cdn) {
	cur_frm.cscript.update_totals(doc);
}

cur_frm.cscript.voucher_type = function(doc, cdt, cdn) {

	if(!doc.company) return;

	var update_jv_details = function(doc, r) {
		$.each(r, function(i, d) {
			var row = frappe.model.add_child(doc, "Journal Entry Account", "accounts");
			row.account = d.account;
			row.balance = d.balance;
		});
		refresh_field("accounts");
	}

	if((!(doc.accounts || []).length) || ((doc.accounts || []).length==1 && !doc.accounts[0].account)) {
		if(in_list(["Cash Entry"], doc.voucher_type)) {
			return frappe.call({
				type: "GET",
				method: "accounting.accounts.doctype.journal_entry.journal_entry.get_default_cash_account",
				args: {
					"account_type": (doc.voucher_type=="Cash Entry" ? "Cash" : null),
					"company": doc.company
				},
				callback: function(r) {
					if(r.message) {
						update_jv_details(doc, [r.message]);
					}
				}
			})
		} else if(doc.voucher_type=="Opening Entry") {
			return frappe.call({
				type:"GET",
				method: "accounting.accounts.doctype.journal_entry.journal_entry.get_opening_accounts",
				args: {
					"company": doc.company
				},
				callback: function(r) {
					frappe.model.clear_table(doc, "accounts");
					if(r.message) {
						update_jv_details(doc, r.message);
					}
					cur_frm.set_value("is_opening", "Yes")
				}
			})
		}
	}
}

frappe.ui.form.on("Journal Entry Account", {
	party: function(frm, cdt, cdn) {
		var d = frappe.get_doc(cdt, cdn);
		if(!d.account && d.party_type && d.party) {
			if(!frm.doc.company) frappe.throw(__("Please select Company"));
			return frm.call({
				method: "accounting.accounts.doctype.journal_entry.journal_entry.get_party_account_and_balance",
				child: d,
				args: {
					company: frm.doc.company,
					party_type: d.party_type,
					party: d.party,
				}
			});
		}
	},

	account: function(frm, dt, dn) {
		accounting.journal_entry.set_account_balance(frm, dt, dn);
	},

	debit: function(frm, dt, dn) {
		cur_frm.cscript.update_totals(frm.doc);
	},

	credit: function(frm, dt, dn) {
		cur_frm.cscript.update_totals(frm.doc);
	},

})

frappe.ui.form.on("Journal Entry Account", "accounts_remove", function(frm) {
	cur_frm.cscript.update_totals(frm.doc);
});

$.extend(accounting.journal_entry, {
	
	quick_entry: function(frm) {
		
		var dialog = new frappe.ui.Dialog({
			title: __("Quick Journal Entry"),
			fields: [
				{fieldtype: "Currency", fieldname: "debit", label: __("Amount"), reqd: 1},
				{fieldtype: "Link", fieldname: "debit_account", label: __("Debit Account"), reqd: 1,
					options: "Account",
					get_query: function() {
						return accounting.journal_entry.account_query(frm);
					}
				},
				{fieldtype: "Link", fieldname: "credit_account", label: __("Credit Account"), reqd: 1,
					options: "Account",
					get_query: function() {
						return accounting.journal_entry.account_query(frm);
					}
				},
				{fieldtype: "Date", fieldname: "posting_date", label: __("Date"), reqd: 1,
					default: frm.doc.posting_date},
				{fieldtype: "Small Text", fieldname: "user_remark", label: __("User Remark")},
			]
		});

		dialog.set_primary_action(__("Save"), function() {
			var btn = this;
			var values = dialog.get_values();

			frm.set_value("posting_date", values.posting_date);
			frm.set_value("user_remark", values.user_remark);
			
			// clear table is used because there might've been an error while adding child
			// and cleanup didn't happen
			frm.clear_table("accounts");

			// using grid.add_new_row() to add a row in UI as well as locals
			// this is required because triggers try to refresh the grid

			var debit_row = frm.fields_dict.accounts.grid.add_new_row();
			frappe.model.set_value(debit_row.doctype, debit_row.name, "account", values.debit_account);
			frappe.model.set_value(debit_row.doctype, debit_row.name, "debit", values.debit);

			var credit_row = frm.fields_dict.accounts.grid.add_new_row();
			frappe.model.set_value(credit_row.doctype, credit_row.name, "account", values.credit_account);
			frappe.model.set_value(credit_row.doctype, credit_row.name, "credit", values.debit);

			frm.save();

			dialog.hide();
		});

		dialog.show();
	},

	account_query: function(frm) {
		var filters = {
			company: frm.doc.company,
			is_group: 0
		};
		return { filters: filters };
	},

	reverse_journal_entry: function(frm) {
		var me = frm.doc;
		for(var i=0; i<me.accounts.length; i++) {
			me.accounts[i].credit += me.accounts[i].debit;
			me.accounts[i].debit = me.accounts[i].credit - me.accounts[i].debit;
			me.accounts[i].credit -= me.accounts[i].debit;
			me.accounts[i].reference_type = "Journal Entry";
			me.accounts[i].reference_name = me.name
		}
		frm.copy_doc();
		cur_frm.reload_doc();
	}
});

$.extend(accounting.journal_entry, {
	set_account_balance: function(frm, dt, dn) {
		var d = locals[dt][dn];
		if(d.account) {
			if(!frm.doc.company) frappe.throw(__("Please select Company first"));
			if(!frm.doc.posting_date) frappe.throw(__("Please select Posting Date first"));

			return frappe.call({
				method: "accounting.accounts.doctype.journal_entry.journal_entry.get_account_balance_and_party_type",
				args: {
					account: d.account,
					date: frm.doc.posting_date,
					company: frm.doc.company,
					debit: flt(d.debit),
					credit: flt(d.credit),
				},
				callback: function(r) {
					if(r.message) {
						$.extend(d, r.message);
						refresh_field('accounts');
					}
				}
			});
		}
	},
});
