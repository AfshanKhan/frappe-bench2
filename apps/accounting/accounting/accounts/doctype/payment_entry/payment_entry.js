// Copyright (c) 2020, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Payment Entry', {

	setup: function(frm) {
		frm.set_query("paid_from", function() {
			var account_types = in_list(["Pay"], frm.doc.payment_type) ?
				["Cash"] : [frappe.boot.party_account_types[frm.doc.party_type]];

			return {
				filters: {
					"account_type": ["in", account_types],
					"is_group": 0,
					"company": frm.doc.company
				}
			}
		});

		frm.set_query("contact_person", function() {
			if (frm.doc.party) {
				return {
					query: 'frappe.contacts.doctype.contact.contact.contact_query',
					filters: {
						link_doctype: frm.doc.party_type,
						link_name: frm.doc.party
					}
				};
			}
		});
		frm.set_query("paid_to", function() {
			var account_types = in_list(["Receive"], frm.doc.payment_type) ?
				["Cash"] : [frappe.boot.party_account_types[frm.doc.party_type]];

			return {
				filters: {
					"account_type": ["in", account_types],
					"is_group": 0,
					"company": frm.doc.company
				}
			}
		});
	},

	refresh: function(frm) {
		frm.events.show_general_ledger(frm);
	},

	show_general_ledger: function(frm) {
		if(frm.doc.docstatus==1) {
			frm.add_custom_button(__('Ledger'), function() {
				frappe.route_options = {
					"voucher_no": frm.doc.name,
					"from_date": frm.doc.posting_date,
					"to_date": frm.doc.posting_date,
					"company": frm.doc.company,
					group_by: ""
				};
				frappe.set_route("query-report", "General Ledger");
			}, "fa fa-table");
		}
	},

	payment_type: function(frm) {
		if(frm.doc.party) {
				frm.events.party(frm);
			}
	},

	party: function(frm) {
		if (frm.doc.contact_email || frm.doc.contact_person) {
			frm.set_value("contact_email", "");
			frm.set_value("contact_person", "");
		}
		if(frm.doc.payment_type && frm.doc.party_type && frm.doc.party) {
			if(!frm.doc.posting_date) {
				frappe.msgprint(__("Please select Posting Date before selecting Party"))
				frm.set_value("party", "");
				return ;
			}
			frm.set_party_account_based_on_party = true;

			return frappe.call({
				method: "accounting.accounts.doctype.payment_entry.payment_entry.get_party_details",
				args: {
					company: frm.doc.company,
					party_type: frm.doc.party_type,
					party: frm.doc.party,
					date: frm.doc.posting_date,
				},
				callback: function(r, rt) {
					if(r.message) {
						console.log(r.message);
						frappe.run_serially([
							() => {
								if(frm.doc.payment_type == "Receive") {
									frm.set_value("paid_from", r.message.party_account);
								} else if (frm.doc.payment_type == "Pay"){
									frm.set_value("paid_to", r.message.party_account);
								}
							},
							() => frm.set_value("party_name", r.message.party_name),
						]);
					}
				}
			});
		}
	},
});
