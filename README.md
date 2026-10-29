<div align="center">
  <img
    src="https://github.com/user-attachments/assets/d0c6cb92-7511-4238-9def-2690461d316d"
    width="200"
    alt="Vuna Sourcing"
    style="border-radius: 20px;"
  />

  <p>Supplier and customer self-service portal for ERPNext</p>

  <p> <a href="https://docs.navari.co.ke/vuna-sourcing">Documentation</a></p>

  [![CI](https://github.com/navariltd/vuna_sourcing/actions/workflows/ci.yml/badge.svg)](https://github.com/navariltd/vuna_sourcing/actions/workflows/ci.yml)


</div>
<div align="center">
	<img width="1440" alt="Vuna Sourcing portal" src="https://github.com/user-attachments/assets/425dc320-7db7-4bad-827e-24b51876e95c" />

	
</div>


## Vuna Sourcing

**Vuna Sourcing** is a self-service portal for **ERPNext**, built on the **Frappe Framework**.

Suppliers and customers sign in to one portal. There they apply to work with you, answer requests for quotation, bid in live auctions, place orders, follow their invoices and ask for credit notes, with no emails, phone calls or paper forms. Everything they do creates standard ERPNext documents, so your buying, selling and accounts keep running through the usual ERPNext workflow.

The portal is at `https://<your-site>/vuna-sourcing` and works on both computers and phones.

### Key Features

* **Self-Service Onboarding** - New suppliers and customers apply online, by invitation or open sign-up. They enter business details, contacts, addresses and bank details, and upload the documents you require. Staff approve applications in ERPNext, which creates the Supplier or Customer and links the portal user.
* **Requests for Quotation** - Suppliers see the RFQs sent to them, enter a price and lead time for each item, save drafts, or decline to quote.
* **Sealed Bids** - Quotations stay hidden from everyone, including staff, until bidding closes and the opening committee opens them together.
* **Open Bids (Live Auctions)** - Suppliers bid against each other in real time and can lower their price until the deadline. See [How open bids work](#how-open-bids-work).
* **Awards** - Award a whole RFQ or individual items to one or more suppliers. Purchase orders can be created automatically on award.
* **Customer Ordering** - Customers order from your item catalogue at their own price list, choose a delivery date and address, and can save an order as a draft.
* **Credit Note Requests** - Customers request credit on an invoice for damaged, short or wrong goods. Accounts approve, reject or return each request in ERPNext.
* **Account Overview** - Suppliers and customers see their open documents, amounts outstanding and overdue, and their invoice history at a glance.
* **Documents in One Place** - Quotations, orders, delivery notes, invoices, debit and credit notes, all ready to print.
* **One Login, Both Roles** - A business that is both a supplier and a customer switches between the two from one account.
* **Phone Friendly** - On a phone the portal has its own layout, with a bottom menu bar.

## How Open Bids Work
An open bid is a reverse auction. Every invited supplier competes on price until the closing time.

1. **First bid.** A supplier must place a bid before they can see anyone else's prices.
2. **Bid room.** After that first bid, they see a countdown, their rank, their own total and the lowest total so far.
3. **Item by item.** Each line shows the lowest price offered for that item next to the supplier's own price. **Take Lead** fills in the lowest price on every line in one click.
4. **Bid again.** Each new bid replaces the supplier's previous one, as many times as they like until bidding closes.
5. **Leaderboard.** Bidders are ranked by total price and the board updates live. Other suppliers appear only as *Bidder A*, *Bidder B* and so on, never by name. When two totals are equal, the earlier bid ranks higher.
6. **Live bid panel.** While an auction is running, a corner panel on every page shows the time left and the supplier's position.

Every bid is saved in an **RFQ Bid Log** that no one can edit or delete. The log gives you a full audit trail of each supplier's prices over time. Once bidding closes, staff review the latest bid from each supplier and make the award. The lowest price does not win automatically.

## Basic Usage

### Suppliers

1. Open **Request for Quotation** and pick a request from the **Invited** tab.
2. Enter a price and lead time for each item and choose how long the prices are valid.
3. Click **Place bid** for an open bid, or **Send quotation** for a sealed bid.
4. Follow the outcome under **Supplier Quotation**, then follow orders and payments under **Purchase Order** and **Purchase Invoice**.

### Customers

1. Open **Sales Order → New** and add items from the catalogue.
2. Choose a delivery date and address, then click **Send order**.
3. Follow deliveries and invoices under **Delivery Note**, **Sales Invoice** and **Pending Invoices**.
4. To ask for a credit, open **Credit Note Request → New**, choose the invoice, the items and a reason.


## Under the Hood

* [**Frappe Framework**](https://github.com/frappe/frappe) - backend, database, authentication, permissions, realtime updates and API layer.
* [**ERPNext**](https://github.com/frappe/erpnext) - suppliers, customers, items, RFQs, quotations, orders, invoices and accounting.
* [**Frappe UI**](https://github.com/frappe/frappe-ui) and [**Vue 3**](https://vuejs.org/) - the portal interface.
* [**Tailwind CSS**](https://tailwindcss.com/) - styling.

## Production Setup

### Managed Hosting

Vuna Sourcing can be deployed on [Frappe Cloud](https://frappecloud.com/). In your bench group, click **Apps → Add App → Add from GitHub**, enter `https://github.com/navariltd/vuna_sourcing`, deploy, then install the app on your site.

### Self Hosting

```bash
bench get-app https://github.com/navariltd/vuna_sourcing --branch develop
bench --site [your-site] install-app vuna_sourcing
bench build --app vuna_sourcing
bench restart
```

## Development Setup

### Manual Installation

1. Set up a Frappe bench (version 16) by following the [Frappe installation guide](https://docs.frappe.io/framework/user/en/installation), then start it:

   ```bash
   bench start
   ```

2. In another terminal, create a site:

   ```bash
   bench new-site sourcing.localhost
   bench --site sourcing.localhost set-config developer_mode 1
   ```

3. Install ERPNext:

   ```bash
   bench get-app erpnext --branch version-16
   bench --site sourcing.localhost install-app erpnext
   ```

4. Get and install Vuna Sourcing:

   ```bash
   bench get-app https://github.com/navariltd/vuna_sourcing --branch develop
   bench --site sourcing.localhost install-app vuna_sourcing
   ```

5. Build the assets and migrate:

   ```bash
   bench build --app vuna_sourcing
   bench --site sourcing.localhost migrate
   ```

6. Open the site, finish the ERPNext setup wizard in Desk, then open the portal:

   ```text
   http://sourcing.localhost:8000/app
   http://sourcing.localhost:8000/vuna-sourcing
   ```

### Portal Development

To work on the portal with live reload, run the Vite dev server while `bench start` is running:

```bash
cd apps/vuna_sourcing
npm install
npm run dev
```

### Running Tests

```bash
bench --site sourcing.localhost set-config allow_tests true
bench --site sourcing.localhost run-tests --app vuna_sourcing
```

## Contributing

This project uses `pre-commit` for formatting and linting. Install and enable it inside the repository:

```bash
cd apps/vuna_sourcing
pre-commit install
```

The configured checks are:

* ruff
* eslint
* prettier
* pyupgrade

## CI

GitHub Actions runs these workflows:

* **CI** - installs the app and runs the unit tests on every push to `develop`.
* **Linters** - runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.

## License

MIT
