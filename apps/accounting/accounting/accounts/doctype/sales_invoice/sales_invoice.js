// Copyright (c) 2020, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sales Invoice', {
	refresh: function(frm) {
		var temp = cur_frm.doc.items;
		var sum = 0;
		var qty = 0;
		for ( var i = 0; i < temp.length; i++)
		{
		var obj = temp[i];
		var amount = obj.amount;
		sum = sum + amount;
		var per_qty = obj.qty;
		qty = qty + per_qty;
    	}
		frm.set_value("total",sum)
		frm.set_value("total_qty", qty)
	}

});

frappe.provide("accounting.accounts");

cur_frm.fields_dict.cash_bank_account.get_query = function(doc) {
	return {
		filters: [
			["Account", "account_type", "in", ["Cash"]],
			["Account", "is_group", "=",0],
			["Account", "company", "=", doc.company],
			["Account", "report_type", "=", "Balance Sheet"]
		]
	}
}

cur_frm.fields_dict['debit_to'].get_query = function(doc) {
	// filter on Account
	return {
		filters: {
			'account_type': 'Receivable',
			'is_group': 0,
			'company': doc.company
		}
	}
}

cur_frm.set_query("income_account", "items", function(doc) {
	return {
		query: "accounting.accounts.doctype.account.account.get_income_account",
		filters: {'company': doc.company }
	}
});

cur_frm.cscript.income_account = function(doc, cdt, cdn){
	var d = locals[cdt][cdn];
	if(d.idx == 1 && d.income_account){
		var cl = doc.items || [];
		for(var i = 0; i < cl.length; i++){
			if(!cl[i].income_account) cl[i].income_account = d.income_account;
		}
	}
	refresh_field('items');
}


frappe.ui.form.on("Sales Invoice Item", "rate", function(frm, cdt, cdn){
	var d = frappe.get_doc(cdt, cdn);
	var amount = parseFloat(d.qty) * parseFloat(d.rate)
	frappe.model.set_value(cdt, cdn, "amount", amount);
	// frappe.model.set_value(cdt, cdn, "stock_qty", d.qty);
	frm.refresh()
})
