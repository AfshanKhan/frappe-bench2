# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		# {
		# 	"module_name": "Accounting",
		# 	"color": "grey",
		# 	"icon": "octicon octicon-file-directory",
		# 	"type": "module",
		# 	"label": _("Accounting")
		# }
		# Modules
		{
			"module_name": "Getting Started",
			"category": "Modules",
			"label": _("Getting Started"),
			"color": "#1abc9c",
			"icon": "fa fa-check-square-o",
			"type": "module",
			# "disable_after_onboard": 1,
			"description": "Dive into the basics for your organisation's needs.",
			# "onboard_present": 1
		},
		{
			"module_name": "Accounts",
			"category": "Modules",
			"label": _("Accounting"),
			"color": "#3498db",
			"icon": "octicon octicon-repo",
			"type": "module",
			"description": "Accounts, billing, payments, cost center and budgeting."
		},
		{
			"module_name": "Selling",
			"category": "Modules",
			"label": _("Selling"),
			"color": "#1abc9c",
			"icon": "octicon octicon-tag",
			"type": "module",
			"description": "Sales orders, quotations, customers and items."
		},
		{
			"module_name": "Buying",
			"category": "Modules",
			"label": _("Buying"),
			"color": "#c0392b",
			"icon": "octicon octicon-briefcase",
			"type": "module",
			"description": "Purchasing, suppliers, material requests, and items."
		},
		{
			"module_name": "Stock",
			"category": "Modules",
			"label": _("Stock"),
			"color": "#f39c12",
			"icon": "octicon octicon-package",
			"type": "module",
			"description": "Stock transactions, reports, serial numbers and batches."
		},
	]

