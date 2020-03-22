// // Copyright (c) 2020, Frappe and contributors
// // For license information, please see license.txt

frappe.ui.form.on('Purchase Invoice', {
	refresh: function(frm) {
		var temp = cur_frm.doc.items;
		var sum = 0;
		var qty = 0;
		for ( var i = 0; i < temp.length; i++)
		{
		var obj = temp[i];
		var amount = obj.amount;
		sum = sum + amount;
		var per_qty = obj.received_qty;
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

cur_frm.fields_dict['credit_to'].get_query = function(doc) {
	// filter on Account
	return {
		filters: {
			'account_type': 'Payable',
			'is_group': 0,
			'company': doc.company
		}
	}
}

cur_frm.set_query("expense_account", "items", function(doc) {
	return {
		query: "accounting.accounts.doctype.account.account.get_expense_account",
		filters: {'company': doc.company }
	}
});

cur_frm.cscript.expense_account = function(doc, cdt, cdn){
	var d = locals[cdt][cdn];
	if(d.idx == 1 && d.expense_account){
		var cl = doc.items || [];
		for(var i = 0; i < cl.length; i++){
			if(!cl[i].expense_account) cl[i].expense_account = d.expense_account;
		}
	}
	refresh_field('items');
}


frappe.ui.form.on("Purchase Invoice Item", "rate", function(frm, cdt, cdn){
	var d = frappe.get_doc(cdt, cdn);
	var amount = parseFloat(d.received_qty) * parseFloat(d.rate)
	frappe.model.set_value(cdt, cdn, "amount", amount);
	frappe.model.set_value(cdt, cdn, "stock_qty", d.received_qty);
	frm.refresh()
})
