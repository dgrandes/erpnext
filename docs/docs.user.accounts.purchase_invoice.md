---
{
	"_label": "Purchase Invoice"
}
---
Purchase Invoice is the exact opposite of your Sales Invoice. It is the bill that your Supplier sends your for products or services delivered. Here you accrue expenses to your Supplier. Making a Purchase Invoice is very similar to making a Purchase Order.

To make a new Purchase Invoice, go to:

> Accounts > Purchase Invoice > New Purchase Invoice

or click on “Make Purchase Invoice” in Purchase Order or Purchase Receipt.

The concept of “Posting Date” is again same as Sales Invoice. “Bill No” and “Bill Date” help you track the bill number as set by your Supplier for reference.

#### Accounting Impact

Like in Sales Invoice, you have to enter an Expense or Asset account for each row in your Items table to indicate if the Item is an Asset or an Expense. You must also enter a Cost Center.  These can also be set in the Item master.

The Purchase Invoice will affect your accounts as follows:

Accounting entries (GL Entry) for a typical double entry “purchase”:

Debits:

- Expense or Asset (net totals, excluding taxes)
- Taxes (assets if VAT-type or expense again).

Credits:

- Supplier

To see entries in your Purchase Invoice after you “Submit”, click on “View Ledger”.

---

#### Is a purchase an “Expense” or “Asset”?

If the Item is consumed immediately on purchase or if it is a service, then the purchase becomes an “Expense”. For example, a telephone bill or travel bill is an “Expense” - it is already consumed.

For inventory Items, that have a value, these purchases are not yet “Expense”, because they still have a value while they remain in your stock. They are “Assets”. If they are raw-materials (used in a process), they will become “Expense” the moment they are consumed in the process. If they are to be sold to a Customer, the become “Expense” when you ship them to the Customer.

Note: In ERPNext, this conversion from “Asset” to “Expense” is not clear. As of the current version, you will have to manually convert an item from an “Asset” to “Expense” via a Journal Voucher. We know its a shortcoming and will be fixed in an upcoming version pretty soon.

---

#### Deducting Taxes at Source

In many countries, your laws may require to deduct taxes by a standard rate when you make payments to your Suppliers. Under these type of schemes, typically if a Supplier crosses a certain threshold of payment and if the type of product is taxable, you may have to deduct some tax (that you pay back to your government, on your Supplier’s behalf).

To do this, you will have to make a new Tax Account under “Tax Liabilities” or similar and credit this Account by the percent you are bound to deduct for every transaction.

For more help, please contact your Accountant!