# ERPNext - web based ERP (http://erpnext.com)
# Copyright (C) 2012 Web Notes Technologies Pvt Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals
import webnotes

from webnotes.utils import add_days, cint, cstr, default_fields, flt, getdate, now, nowdate

from webnotes.model.doc import addchild
from webnotes.model.utils import getlist
from webnotes.model.controller import get_obj
from webnotes import form, msgprint


	

from utilities.transaction_base import TransactionBase




class DocType(TransactionBase):
	def __init__(self,d,dl):
		self.doc, self.doclist = d,dl

		self.doctype_dict = {
			'Sales Order'		: 'Sales Order Item',
			'Delivery Note'		: 'Delivery Note Item',
			'Sales Invoice':'Sales Invoice Item',
			'Installation Note' : 'Installation Note Item'
		}
												 
		self.ref_doctype_dict= {}

		self.next_dt_detail = {
			'delivered_qty' : 'Delivery Note Item',
			'billed_qty'		: 'Sales Invoice Item',
			'installed_qty' : 'Installation Note Item'}

		self.msg = []


	def get_contact_details(self, obj = '', primary = 0):
		cond = " and contact_name = '"+cstr(obj.doc.contact_person)+"'"
		if primary: cond = " and is_primary_contact = 'Yes'"
		contact = webnotes.conn.sql("select contact_name, contact_no, email_id, contact_address from `tabContact` where customer = '%s' and docstatus != 2 %s" %(obj.doc.customer, cond), as_dict = 1)
		if not contact:
			return
		c = contact[0]
		obj.doc.contact_person = c['contact_name'] or ''
		obj.doc.contact_no = c['contact_no'] or ''
		obj.doc.email_id = c['email_id'] or ''
		obj.doc.customer_mobile_no = c['contact_no'] or ''
		if c['contact_address']:
			obj.doc.customer_address = c['contact_address']


	def get_shipping_details(self, obj = ''):
		det = webnotes.conn.sql("select name, ship_to, shipping_address from `tabShipping Address` where customer = '%s' and docstatus != 2 and ifnull(is_primary_address, 'Yes') = 'Yes'" %(obj.doc.customer), as_dict = 1)
		obj.doc.ship_det_no = det and det[0]['name'] or ''
		obj.doc.ship_to = det and det[0]['ship_to'] or ''
		obj.doc.shipping_address = det and det[0]['shipping_address'] or ''


	def get_invoice_details(self, obj = ''):
		if obj.doc.company:
			acc_head = webnotes.conn.sql("select name from `tabAccount` where name = '%s' and docstatus != 2" % (cstr(obj.doc.customer) + " - " + get_value('Company', obj.doc.company, 'abbr')))
			obj.doc.debit_to = acc_head and acc_head[0][0] or ''

	


	def get_serial_details(self, serial_no, obj):
		import json
		item = webnotes.conn.sql("select item_code, make, label,brand, description from `tabSerial No` where name = '%s' and docstatus != 2" %(serial_no), as_dict=1)
		tax = webnotes.conn.sql("select tax_type, tax_rate from `tabItem Tax` where parent = %s" , item[0]['item_code'])
		t = {}
		for x in tax: t[x[0]] = flt(x[1])
		ret = {
			'item_code'				: item and item[0]['item_code'] or '',
			'make'						 : item and item[0]['make'] or '',
			'label'						: item and item[0]['label'] or '',
			'brand'						: item and item[0]['brand'] or '',
			'description'			: item and item[0]['description'] or '',
			'item_tax_rate'		: json.dumps(t)
		}
		return ret
		

	def get_rate(self, arg):
		arg = eval(arg)
		rate = webnotes.conn.sql("select account_type, tax_rate from `tabAccount` where name = '%s' and docstatus != 2" %(arg['account_head']), as_dict=1)
		ret = {'rate' : 0}
		if arg['charge_type'] == 'Actual' and rate[0]['account_type'] == 'Tax':
			msgprint("You cannot select ACCOUNT HEAD of type TAX as your CHARGE TYPE is 'ACTUAL'")
			ret = {
				'account_head'	:	''
			}
		elif rate[0]['account_type'] in ['Tax', 'Chargeable'] and not arg['charge_type'] == 'Actual':
			ret = {
				'rate'	:	rate and flt(rate[0]['tax_rate']) or 0
			}
		return ret


	def get_item_list(self, obj, is_stopped=0):
		"""get item list"""
		il = []
		for d in getlist(obj.doclist,obj.fname):
			reserved_wh, reserved_qty = '', 0		# used for delivery note
			qty = flt(d.qty)
			if is_stopped:
				qty = flt(d.qty) > flt(d.delivered_qty) and flt(flt(d.qty) - flt(d.delivered_qty)) or 0
				
			if d.prevdoc_doctype == 'Sales Order':
				# used in delivery note to reduce reserved_qty 
				# Eg.: if SO qty is 10 and there is tolerance of 20%, then it will allow DN of 12.
				# But in this case reserved qty should only be reduced by 10 and not 12.

				tot_qty, max_qty, tot_amt, max_amt, reserved_wh = self.get_curr_and_ref_doc_details(d.doctype, 'prevdoc_detail_docname', d.prevdoc_detail_docname, obj.doc.name, obj.doc.doctype)
				if((flt(tot_qty) + flt(qty) > flt(max_qty))):
					reserved_qty = -(flt(max_qty)-flt(tot_qty))
				else:	
					reserved_qty = - flt(qty)
					
			if obj.doc.doctype == 'Sales Order':
				reserved_wh = d.warehouse
						
			if self.has_sales_bom(d.item_code):
				for p in getlist(obj.doclist, 'delivery_note_packing_items'):
					if p.parent_detail_docname == d.name and p.parent_item == d.item_code:
						# the packing details table's qty is already multiplied with parent's qty
						il.append({
							'warehouse': p.warehouse,
							'warehouse': reserved_wh,
							'item_code': p.item_code,
							'qty': flt(p.qty),
							'reserved_qty': (flt(p.qty)/qty)*(reserved_qty),
							'uom': p.uom,
							'batch_no': p.batch_no,
							'serial_no': p.serial_no,
							'name': d.name
						})
			else:
				il.append({
					'warehouse': d.warehouse,
					'warehouse': reserved_wh,
					'item_code': d.item_code,
					'qty': qty,
					'reserved_qty': reserved_qty,
					'uom': d.stock_uom,
					'batch_no': d.batch_no,
					'serial_no': d.serial_no,
					'name': d.name
				})
		return il


	def get_curr_and_ref_doc_details(self, curr_doctype, ref_tab_fname, ref_tab_dn, curr_parent_name, curr_parent_doctype):
		""" Get qty, amount already billed or delivered against curr line item for current doctype
			For Eg: SO-RV get total qty, amount from SO and also total qty, amount against that SO in RV
		"""
		#Get total qty, amt of current doctype (eg RV) except for qty, amt of this transaction
		if curr_parent_doctype == 'Installation Note':
			curr_det = webnotes.conn.sql("select sum(qty) from `tab%s` where %s = '%s' and docstatus = 1 and parent != '%s'"% (curr_doctype, ref_tab_fname, ref_tab_dn, curr_parent_name))
			qty, amt = curr_det and flt(curr_det[0][0]) or 0, 0
		else:
			curr_det = webnotes.conn.sql("select sum(qty), sum(amount) from `tab%s` where %s = '%s' and docstatus = 1 and parent != '%s'"% (curr_doctype, ref_tab_fname, ref_tab_dn, curr_parent_name))
			qty, amt = curr_det and flt(curr_det[0][0]) or 0, curr_det and flt(curr_det[0][1]) or 0

		# get total qty of ref doctype
		so_det = webnotes.conn.sql("select qty, amount, warehouse from `tabSales Order Item` where name = '%s' and docstatus = 1"% ref_tab_dn)
		max_qty, max_amt, res_wh = so_det and flt(so_det[0][0]) or 0, so_det and flt(so_det[0][1]) or 0, so_det and cstr(so_det[0][2]) or ''
		return qty, max_qty, amt, max_amt, res_wh


	# Make Packing List from Sales BOM
	# =======================================================================
	def has_sales_bom(self, item_code):
		return webnotes.conn.sql("select name from `tabSales BOM` where new_item_code=%s and docstatus != 2", item_code)
	
	def get_sales_bom_items(self, item_code):
		return webnotes.conn.sql("""select t1.item_code, t1.qty, t1.uom 
			from `tabSales BOM Item` t1, `tabSales BOM` t2 
			where t2.new_item_code=%s and t1.parent = t2.name""", item_code, as_dict=1)

	def get_packing_item_details(self, item):
		return webnotes.conn.sql("select item_name, description, stock_uom from `tabItem` where name = %s", item, as_dict = 1)[0]

	def get_bin_qty(self, item, warehouse):
		det = webnotes.conn.sql("select actual_qty, projected_qty from `tabBin` where item_code = '%s' and warehouse = '%s'" % (item, warehouse), as_dict = 1)
		return det and det[0] or ''

	def update_packing_list_item(self,obj, packing_item_code, qty, warehouse, line):
		bin = self.get_bin_qty(packing_item_code, warehouse)
		item = self.get_packing_item_details(packing_item_code)

		# check if exists
		exists = 0
		for d in getlist(obj.doclist, 'delivery_note_packing_items'):
			if d.parent_item == line.item_code and d.item_code == packing_item_code and d.parent_detail_docname == line.name:
				pi, exists = d, 1
				break

		if not exists:
			pi = addchild(obj.doc, 'delivery_note_packing_items', 'Delivery Note Packing Item', 1, obj.doclist)

		pi.parent_item = line.item_code
		pi.item_code = packing_item_code
		pi.item_name = item['item_name']
		pi.parent_detail_docname = line.name
		pi.description = item['description']
		pi.uom = item['stock_uom']
		pi.qty = flt(qty)
		pi.actual_qty = bin and flt(bin['actual_qty']) or 0
		pi.projected_qty = bin and flt(bin['projected_qty']) or 0
		if not pi.warehouse:
			pi.warehouse = warehouse
		if not pi.batch_no:
			pi.batch_no = cstr(line.batch_no)
		pi.idx = self.packing_list_idx
		
		# saved, since this function is called on_update of delivery note
		pi.save()
		
		self.packing_list_idx += 1


	def make_packing_list(self, obj, fname):
		"""make packing list for sales bom item"""
		self.packing_list_idx = 0
		parent_items = []
		for d in getlist(obj.doclist, fname):
			warehouse = fname == "sales_order_items" and d.warehouse or d.warehouse
			if self.has_sales_bom(d.item_code):
				for i in self.get_sales_bom_items(d.item_code):
					self.update_packing_list_item(obj, i['item_code'], flt(i['qty'])*flt(d.qty), warehouse, d)

				if [d.item_code, d.name] not in parent_items:
					parent_items.append([d.item_code, d.name])
				
		obj.doclist = self.cleanup_packing_list(obj, parent_items)
		
		return obj.doclist
		
	def cleanup_packing_list(self, obj, parent_items):
		"""Remove all those child items which are no longer present in main item table"""
		delete_list = []
		for d in getlist(obj.doclist, 'delivery_note_packing_items'):
			if [d.parent_item, d.parent_detail_docname] not in parent_items:
				# mark for deletion from doclist
				delete_list.append(d.name)

		if not delete_list:
			return obj.doclist
		
		# delete from doclist
		obj.doclist = filter(lambda d: d.name not in delete_list, obj.doclist)
		
		# delete from db
		webnotes.conn.sql("""\
			delete from `tabDelivery Note Packing Item`
			where name in (%s)"""
			% (", ".join(["%s"] * len(delete_list))),
			tuple(delete_list))
			
		return obj.doclist

	# Get total in words
	# ==================================================================	
	def get_total_in_words(self, currency, amount):
		from webnotes.utils import money_in_words
		return money_in_words(amount, currency)
		

	# Get month based on date (required in sales person and sales partner)
	# ========================================================================
	def get_month(self,date):
		month_list = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
		month_idx = cint(cstr(date).split('-')[1])-1
		return month_list[month_idx]
		
		
	# **** Check for Stop SO as no transactions can be made against Stopped SO. Need to unstop it. ***
	def check_stop_sales_order(self,obj):
		for d in getlist(obj.doclist,obj.fname):
			ref_doc_name = ''
			if d.fields.has_key('prevdoc_docname') and d.prevdoc_docname and d.prevdoc_doctype == 'Sales Order':
				ref_doc_name = d.prevdoc_docname
			elif d.fields.has_key('sales_order') and d.sales_order and not d.delivery_note:
				ref_doc_name = d.sales_order
			if ref_doc_name:
				so_status = webnotes.conn.sql("select status from `tabSales Order` where name = %s",ref_doc_name)
				so_status = so_status and so_status[0][0] or ''
				if so_status == 'Stopped':
					msgprint("You cannot do any transaction against Sales Order : '%s' as it is Stopped." %(ref_doc_name))
					raise Exception
					
					
	def check_credit(self,obj,grand_total):
		acc_head = webnotes.conn.sql("select name from `tabAccount` where company = '%s' and master_name = '%s'"%(obj.doc.company, obj.doc.customer))
		if acc_head:
			tot_outstanding = 0
			dbcr = webnotes.conn.sql("select sum(debit), sum(credit) from `tabGL Entry` where account = '%s' and ifnull(is_cancelled, 'No')='No'" % acc_head[0][0])
			if dbcr:
				tot_outstanding = flt(dbcr[0][0])-flt(dbcr[0][1])

			exact_outstanding = flt(tot_outstanding) + flt(grand_total)
			get_obj('Account',acc_head[0][0]).check_credit_limit(acc_head[0][0], obj.doc.company, exact_outstanding)

	def validate_fiscal_year(self,fiscal_year,posting_date,dn):
		fy=webnotes.conn.sql("select year_start_date from `tabFiscal Year` where name='%s'"%fiscal_year)
		ysd=fy and fy[0][0] or ""
		yed=add_days(str(ysd),365)
		if str(posting_date) < str(ysd) or str(posting_date) > str(yed):
			msgprint("%s not within the fiscal year"%(dn))
			raise Exception


	# get against document date	self.prevdoc_date_field
	#-----------------------------
	def get_prevdoc_date(self, obj):
		import datetime
		for d in getlist(obj.doclist, obj.fname):
			if d.prevdoc_doctype and d.prevdoc_docname:
				if d.prevdoc_doctype == 'Sales Invoice':
					dt = webnotes.conn.sql("select posting_date from `tab%s` where name = '%s'" % (d.prevdoc_doctype, d.prevdoc_docname))
				else:
					dt = webnotes.conn.sql("select posting_date from `tab%s` where name = '%s'" % (d.prevdoc_doctype, d.prevdoc_docname))
				d.prevdoc_date = (dt and dt[0][0]) and dt[0][0].strftime('%Y-%m-%d') or ''

	def update_prevdoc_detail(self, is_submit, obj):
		StatusUpdater(obj, is_submit).update()




#
# make item code readonly if (detail no is set)
#


class StatusUpdater:
	"""
		Updates the status of the calling records
		
		From Delivery Note 
			- Update Delivered Qty
			- Update Percent
			- Validate over delivery
			
		From Sales Invoice 
			- Update Billed Amt
			- Update Percent
			- Validate over billing
			
		From Installation Note
			- Update Installed Qty
			- Update Percent Qty
			- Validate over installation
	"""
	def __init__(self, obj, is_submit):
		self.obj = obj # caller object
		self.is_submit = is_submit
		self.tolerance = {}
		self.global_tolerance = None
	
	def update(self):
		self.update_all_qty()
		self.validate_all_qty()
	
	def validate_all_qty(self):
		"""
			Validates over-billing / delivery / installation in Delivery Note, Sales Invoice, Installation Note
			To called after update_all_qty
		"""
		if self.obj.doc.doctype=='Delivery Note':
			self.validate_qty({
				'source_dt'		:'Delivery Note Item',
				'compare_field'	:'delivered_qty',
				'compare_ref_field'	:'qty',
				'target_dt'		:'Sales Order Item',
				'join_field'	:'prevdoc_detail_docname'
			})
		elif self.obj.doc.doctype=='Sales Invoice':
			self.validate_qty({
				'source_dt'		:'Sales Invoice Item',
				'compare_field'	:'billed_amt',
				'compare_ref_field'	:'print_amount',
				'target_dt'		:'Sales Order Item',
				'join_field'	:'sales_order_item'
			})
			self.validate_qty({
				'source_dt'		:'Sales Invoice Item',
				'compare_field'	:'billed_amt',
				'compare_ref_field'	:'print_amount',
				'target_dt'		:'Delivery Note Item',
				'join_field'	:'delivery_note_item'
			}, no_tolerance =1)
		elif self.obj.doc.doctype=='Installation Note':
			self.validate_qty({
				'source_dt'		:'Installation Item Details',
				'compare_field'	:'installed_qty',
				'compare_ref_field'	:'qty',
				'target_dt'		:'Delivery Note Item',
				'join_field'	:'delivery_note_item'
			}, no_tolerance =1)

	
	def get_tolerance_for(self, item_code):
		"""
			Returns the tolerance for the item, if not set, returns global tolerance
		"""
		if self.tolerance.get(item_code):
			return self.tolerance[item_code]
		
		tolerance = flt(get_value('Item',item_code,'tolerance') or 0)

		if not(tolerance):
			if self.global_tolerance == None:
				self.global_tolerance = flt(get_value('Global Defaults',None,'tolerance') or 0)
			tolerance = self.global_tolerance
		
		self.tolerance[item_code] = tolerance
		return tolerance
		
	def check_overflow_with_tolerance(self, item, args):
		"""
			Checks if there is overflow condering a relaxation tolerance
		"""
	
		# check if overflow is within tolerance
		tolerance = self.get_tolerance_for(item['item_code'])
		overflow_percent = ((item[args['compare_field']] - item[args['compare_ref_field']]) / item[args['compare_ref_field']] * 100)
	
		if overflow_percent - tolerance > 0.01:
			item['max_allowed'] = flt(item[args['compare_ref_field']] * (100+tolerance)/100)
			item['reduce_by'] = item[args['compare_field']] - item['max_allowed']
		
			msgprint("""
				Row #%(idx)s: Max %(compare_ref_field)s allowed for <b>Item %(item_code)s</b> against <b>%(parenttype)s %(parent)s</b> is <b>%(max_allowed)s</b>. 
				
				If you want to increase your overflow tolerance, please increase tolerance %% in Global Defaults or Item master. 
				
				Or, you must reduce the %(compare_ref_field)s by %(reduce_by)s
				
				Also, please check if the order item has already been billed in the Sales Order""" % item, raise_exception=1)

	def validate_qty(self, args, no_tolerance=None):
		"""
			Validates qty at row level
		"""
		# get unique transactions to update
		for d in self.obj.doclist:
			if d.doctype == args['source_dt']:
				args['name'] = d.fields[args['join_field']]

				# get all qty where qty > compare_field
				item = webnotes.conn.sql("""
					select item_code, `%(compare_ref_field)s`, `%(compare_field)s`, parenttype, parent from `tab%(target_dt)s` 
					where `%(compare_ref_field)s` < `%(compare_field)s` and name="%(name)s" and docstatus=1
					""" % args, as_dict=1)
				if item:
					item = item[0]
					item['idx'] = d.idx
					item['compare_ref_field'] = args['compare_ref_field'].replace('_', ' ')

					if not item[args['compare_ref_field']]:
						msgprint("As %(compare_ref_field)s for item: %(item_code)s in %(parenttype)s: %(parent)s is zero, system will not check over-delivery or over-billed" % item)
					elif no_tolerance:
						item['reduce_by'] = item[args['compare_field']] - item[args['compare_ref_field']]
						if item['reduce_by'] > .01:
							msgprint("""
								Row #%(idx)s: Max %(compare_ref_field)s allowed for <b>Item %(item_code)s</b> against 
								<b>%(parenttype)s %(parent)s</b> is <b>""" % item 
								+ cstr(item[args['compare_ref_field']]) + """</b>. 
							
								You must reduce the %(compare_ref_field)s by %(reduce_by)s""" % item, raise_exception=1)
					
					else:
						self.check_overflow_with_tolerance(item, args)
						
	
	def update_all_qty(self):
		"""
			Updates delivered / billed / installed qty in Sales Order & Delivery Note
		"""
		if self.obj.doc.doctype=='Delivery Note':
			self.update_qty({
				'target_field'			:'delivered_qty',
				'target_dt'				:'Sales Order Item',
				'target_parent_dt'		:'Sales Order',
				'target_parent_field'	:'per_delivered',
				'target_ref_field'		:'qty',
				'source_dt'				:'Delivery Note Item',
				'source_field'			:'qty',
				'join_field'			:'prevdoc_detail_docname',
				'percent_join_field'	:'prevdoc_docname',
				'status_field'			:'delivery_status',
				'keyword'				:'Delivered'
			})
			
		elif self.obj.doc.doctype=='Sales Invoice':
			self.update_qty({
				'target_field'			:'billed_amt',
				'target_dt'				:'Sales Order Item',
				'target_parent_dt'		:'Sales Order',
				'target_parent_field'	:'per_billed',
				'target_ref_field'		:'print_amount',
				'source_dt'				:'Sales Invoice Item',
				'source_field'			:'print_amount',
				'join_field'			:'sales_order_item',
				'percent_join_field'	:'sales_order',
				'status_field'			:'billing_status',
				'keyword'				:'Billed'
			})

			self.update_qty({
				'target_field'			:'billed_amt',
				'target_dt'				:'Delivery Note Item',
				'target_parent_dt'		:'Delivery Note',
				'target_parent_field'	:'per_billed',
				'target_ref_field'		:'print_amount',
				'source_dt'				:'Sales Invoice Item',
				'source_field'			:'print_amount',
				'join_field'			:'delivery_note_item',
				'percent_join_field'	:'delivery_note',
				'status_field'			:'billing_status',
				'keyword'				:'Billed'
			})

		if self.obj.doc.doctype=='Installation Note':
			self.update_qty({
				'target_field'			:'installed_qty',
				'target_dt'				:'Delivery Note Item',
				'target_parent_dt'		:'Delivery Note',
				'target_parent_field'	:'per_installed',
				'target_ref_field'		:'qty',
				'source_dt'				:'Installation Note Item',
				'source_field'			:'qty',
				'join_field'			:'prevdoc_detail_docname',
				'percent_join_field'	:'prevdoc_docname',
				'status_field'			:'installation_status',
				'keyword'				:'Installed'
			})


	def update_qty(self, args):
		"""
			Updates qty at row level
		"""
		# condition to include current record (if submit or no if cancel)
		if self.is_submit:
			args['cond'] = ' or parent="%s"' % self.obj.doc.name
		else:
			args['cond'] = ' and parent!="%s"' % self.obj.doc.name
		
		# update quantities in child table
		for d in self.obj.doclist:
			if d.doctype == args['source_dt']:
				# updates qty in the child table
				args['detail_id'] = d.fields.get(args['join_field'])
			
				if args['detail_id']:
					webnotes.conn.sql("""
						update 
							`tab%(target_dt)s` 
						set 
							%(target_field)s = (select sum(%(source_field)s) from `tab%(source_dt)s` where `%(join_field)s`="%(detail_id)s" and (docstatus=1 %(cond)s))
						where
							name="%(detail_id)s"            
					""" % args)			
		
		# get unique transactions to update
		for name in set([d.fields.get(args['percent_join_field']) for d in self.obj.doclist if d.doctype == args['source_dt']]):
			if name:
				args['name'] = name
				
				# update percent complete in the parent table
				webnotes.conn.sql("""
					update 
						`tab%(target_parent_dt)s` 
					set 
						%(target_parent_field)s = 
							(select sum(if(%(target_ref_field)s > ifnull(%(target_field)s, 0), %(target_field)s, %(target_ref_field)s))/sum(%(target_ref_field)s)*100 from `tab%(target_dt)s` where parent="%(name)s"), 
						modified = now()
					where
						name="%(name)s"
					""" % args)

				# update field
				if args['status_field']:
					webnotes.conn.sql("""
						update
							`tab%(target_parent_dt)s` 
						set
							%(status_field)s = if(ifnull(%(target_parent_field)s,0)<0.001, 'Not %(keyword)s', 
									if(%(target_parent_field)s>=99.99, 'Fully %(keyword)s', 'Partly %(keyword)s')
								)
						where
							name="%(name)s"
					""" % args)

