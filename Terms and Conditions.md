
## Terms and Conditions of Service

**1. Introduction**

Welcome to Vuna Sourcing, a service provided by Navari Limited ("Company", "we", "our", or "us"). By using our service, you agree to be bound by the following terms and conditions ("Terms of Service", "Terms"). Please read these terms carefully before using our service.

**2. Acceptance of Terms**

By installing, accessing or using Vuna Sourcing, you agree to comply with and be bound by these Terms. If you do not agree to these Terms, you must not install, access or use our service.

**3. Changes to Terms**

We reserve the right to modify these Terms at any time. Any changes will be effective immediately upon posting to our website or service. Your continued use of the service following any such changes constitutes your acceptance of the new Terms.

**4. Service Description**

Vuna Sourcing is an open-source supplier and customer self-service portal for ERPNext. It runs on the ERPNext site of the business that installs it (the "Site Owner"). Through it, the Site Owner's suppliers and customers (the "Portal Users") can:

- apply to work with the Site Owner
- respond to requests for quotation and take part in sealed or open bids
- place orders
- follow invoices and account statements
- request credit notes

Navari Limited provides the software only. We are not a party to any quotation, bid, order, invoice or other transaction made through the service. Those are between the Site Owner and its Portal Users.

**5. User Responsibilities**

-   You are responsible for ensuring that your use of Vuna Sourcing complies with all applicable laws and regulations.
-   You must not use the service for any illegal or unauthorized purpose.
-   You must provide accurate information and documents, and keep your login details secure.
-   You must not access, or attempt to access, documents, accounts or branches you have not been given access to.
-   You must not collude with other bidders, or attempt to see or influence other suppliers' sealed bids.
-   Site Owners are responsible for managing who has access to their portal, for the data stored on their site, and for their dealings with Portal Users.

**6. Intellectual Property**

Vuna Sourcing is released under the MIT License. You may use, copy, modify and distribute the software as that license permits. The Vuna Sourcing and Navari names, logos and other branding remain the property of Navari Limited and may not be used without our written permission. Portal Users keep ownership of the information and documents they submit through the service.

**7. Data Privacy**

We respect your privacy and are committed to protecting your personal information. Please review our [Privacy Policy](https://github.com/navariltd/vuna_sourcing/blob/version-16/Privacy%20Policy.md), which outlines how we collect, use, and safeguard your data.

**8. Limitation of Liability**

Navari Limited shall not be liable for any direct, indirect, incidental, special, or consequential damages arising out of or in connection with your use of Vuna Sourcing. This includes, but is not limited to, any loss of data, profits, or business opportunities, and any loss arising from transactions between Site Owners and Portal Users.

**9. Termination**

We reserve the right to suspend or terminate your access to Vuna Sourcing at any time, with or without cause, and with or without notice. Site Owners may also disable a Portal User's access at any time. Upon termination, you must cease all use of the service.

**10. Governing Law**

These Terms are governed by and construed in accordance with the laws of Kenya. Any disputes arising under these Terms shall be subject to the exclusive jurisdiction of the courts of Kenya.

**11. Contact Information**

If you have any questions or concerns regarding these Terms, please contact us at:

Navari Limited
7th Floor, Block I Eden Square Complex, Chiromo Road.
P.O Box 856-00606 Nairobi, Kenya
Email: solutions@navari.co.ke


- **Section 6 (Intellectual Property):** the Burundi text banned copying or reselling, which contradicts this app's MIT license (`hooks.py` declares `app_license = "mit"`). I rewrote it to allow what MIT allows and keep only the name and branding protected. For the same reason I removed "copy, sell, resell" from section 5 and "delete any copies of the software" from section 9.
- **Section 7 (Data Privacy):** the Privacy Policy link assumes you'll save the earlier policy as `Privacy Policy.md` on `develop` in the vuna_sourcing repo, the same way burundi-compliance does. That file doesn't exist yet. Adjust the link if you save it elsewhere.
- **Section 10 (Governing Law):** switched from Burundi to Kenya, since Navari is in Nairobi. Confirm that's what you want.
