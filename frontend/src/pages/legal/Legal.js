import React from 'react';
import { Link } from 'react-router-dom';

const LegalShell = ({ title, lastUpdated, children }) => (
  <div className="min-h-screen bg-[#0d0d1a] text-white" data-testid={`legal-${title.toLowerCase().replace(/\s+/g, '-')}`}>
    <header className="border-b border-[#2a2a45] px-6 py-4">
      <Link to="/" className="text-lg font-extrabold tracking-tight" style={{ fontFamily: 'Plus Jakarta Sans' }}>
        <span style={{ background: 'linear-gradient(90deg, #4f8ef7, #e2b96f)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>GenLeadAI</span>
      </Link>
    </header>
    <main className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-3xl font-extrabold mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>{title}</h1>
      <p className="text-sm text-[#a0a8c0] mb-8">Last updated: {lastUpdated}</p>
      <div className="prose prose-invert max-w-none space-y-4 text-sm text-[#cbd5e1] leading-relaxed">{children}</div>
      <footer className="mt-12 pt-6 border-t border-[#2a2a45] text-xs text-[#a0a8c0]">
        Questions? Email <a href="mailto:meghaagarwal@genleadai.com" className="text-[#4f8ef7]">meghaagarwal@genleadai.com</a>. Jurisdiction: Shillong, Meghalaya, India.
      </footer>
    </main>
  </div>
);

export const Privacy = () => (
  <LegalShell title="Privacy Policy" lastUpdated="May 2026">
    <h2 className="text-xl font-bold text-white mt-6 mb-2">What we collect</h2>
    <p>Aria by GenLeadAI processes the following personal data on behalf of our workspace clients:</p>
    <ul className="list-disc pl-6 space-y-1">
      <li>Lead name, phone number, email</li>
      <li>Conversation content (WhatsApp messages, internal notes)</li>
      <li>Usage data (page views, feature usage, API call metadata)</li>
      <li>Authentication identifiers (email, hashed password, session tokens)</li>
    </ul>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">Purpose</h2>
    <p>AI-powered lead qualification, sales pipeline management, and conversation automation on WhatsApp. Aria does not sell, rent, or share personal data with third parties for advertising.</p>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">Retention</h2>
    <ul className="list-disc pl-6 space-y-1">
      <li>Conversation message bodies: 365 days, then automatically purged (metadata retained)</li>
      <li>Lead profile data: duration of subscription + 90 days grace</li>
      <li>Invoices / payment records: 7 years (legal requirement)</li>
      <li>Audit log: 2 years minimum</li>
      <li>API usage / classification log: 90 days</li>
    </ul>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">Third-party processors</h2>
    <ul className="list-disc pl-6 space-y-1">
      <li><strong>Anthropic</strong> (Claude AI) — sales conversation intelligence</li>
      <li><strong>360dialog</strong> — WhatsApp Business Cloud API gateway</li>
      <li><strong>Supabase / MongoDB Atlas</strong> — application database</li>
      <li><strong>Vercel / Emergent</strong> — hosting infrastructure</li>
      <li><strong>Stripe</strong> — payments (when enabled)</li>
      <li><strong>Resend</strong> — transactional email</li>
    </ul>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">Your rights under DPDP Act 2023</h2>
    <p>You (and the leads we process on your behalf) have the right to:</p>
    <ul className="list-disc pl-6 space-y-1">
      <li>Access — request a copy of personal data we hold</li>
      <li>Correction — fix inaccurate or outdated information</li>
      <li>Erasure — request anonymisation or hard deletion of personal data</li>
      <li>Grievance redressal — contact our Data Protection Officer below</li>
    </ul>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">Data Protection Officer</h2>
    <p>Megha Agarwal · <a href="mailto:meghaagarwal@genleadai.com" className="text-[#4f8ef7]">meghaagarwal@genleadai.com</a> · Shillong, Meghalaya, India · GSTIN 17BVKPA9777N1ZP</p>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">Security</h2>
    <p>All credentials (CRM tokens, WhatsApp API keys) are encrypted at rest with AES-128-GCM (Fernet). Inbound API endpoints are rate-limited. RLS-equivalent tenant scoping is enforced at the application layer.</p>
  </LegalShell>
);

export const Terms = () => (
  <LegalShell title="Terms of Service" lastUpdated="May 2026">
    <h2 className="text-xl font-bold text-white mt-6 mb-2">1. Service</h2>
    <p>Aria by GenLeadAI is a multi-tenant SaaS platform for AI-driven sales pipeline management. Subscription terms (DIY / DWY / DFY) are described at <Link to="/billing" className="text-[#4f8ef7]">/billing</Link>.</p>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">2. Client responsibilities</h2>
    <ul className="list-disc pl-6 space-y-1">
      <li>You are responsible for obtaining WhatsApp opt-in consent from every lead you add to Aria.</li>
      <li>You agree not to use Aria for spam, harassment, or content that violates Meta's WhatsApp Business Messaging Policy.</li>
      <li>You agree not to use Aria to message minors or for content unlawful in India or the lead's jurisdiction.</li>
    </ul>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">3. Acceptable use</h2>
    <p>Prohibited activities include: bulk unsolicited outreach, sending illegal/obscene/defamatory content, attempting to circumvent rate limits or RLS, reverse-engineering Aria's classification or touchpoint engine, and reselling Aria as your own product.</p>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">4. Limitation of liability</h2>
    <p>GenLeadAI is not liable for WhatsApp account suspensions or bans caused by client misuse, third-party API outages (Anthropic, 360dialog, Meta), or revenue loss arising from missed messages. Total liability is capped at fees paid by the client in the 3 months prior to the claim.</p>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">5. Intellectual property</h2>
    <p>GenLeadAI owns all platform IP including (without limitation) the Aria classification system, touchpoint engine, sync engine, and confidence score algorithm. Client retains ownership of its own lead data and uploaded content.</p>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">6. Payment & refunds</h2>
    <p>Subscriptions billed monthly. 14-day free trial available on DIY and DWY. Refunds: pro-rata refund within 7 days of first payment if Aria provably failed to operate as described. After that, no refunds.</p>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">7. Termination</h2>
    <p>Either party may terminate with 30 days' written notice. On termination, lead data retained for 90 days then purged. Invoices retained 7 years.</p>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">8. Governing law</h2>
    <p>These terms are governed by the laws of India. Disputes are subject to the exclusive jurisdiction of courts in Shillong, Meghalaya.</p>
  </LegalShell>
);

export const DPA = () => (
  <LegalShell title="Data Processing Agreement" lastUpdated="May 2026">
    <h2 className="text-xl font-bold text-white mt-6 mb-2">1. Parties & roles</h2>
    <p>GenLeadAI acts as <strong>Data Processor</strong>. The client (workspace owner) acts as <strong>Data Controller</strong> for all lead and contact data processed within their workspace.</p>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">2. DPDP Act 2023 compliance</h2>
    <p>This DPA is designed to satisfy obligations under the Digital Personal Data Protection Act 2023 (India) and is supplementary to our Terms of Service.</p>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">3. Sub-processors</h2>
    <p>GenLeadAI engages the following sub-processors. Material changes will be notified 30 days in advance.</p>
    <ul className="list-disc pl-6 space-y-1">
      <li>Anthropic PBC (Claude API) — US, EU-compliant</li>
      <li>360dialog GmbH (WhatsApp Business gateway) — Germany</li>
      <li>MongoDB Atlas — global, encryption at rest</li>
      <li>Vercel / Emergent — hosting</li>
      <li>Stripe Payments India Pvt Ltd — payment processing (when enabled)</li>
    </ul>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">4. Security measures</h2>
    <ul className="list-disc pl-6 space-y-1">
      <li>AES-128-GCM (Fernet) encryption at rest for stored credentials</li>
      <li>TLS in transit for all API and webhook traffic</li>
      <li>Tenant isolation enforced at the application + query layer</li>
      <li>Rate limiting on auth + webhook endpoints</li>
      <li>Append-only audit log of all data-modifying actions</li>
      <li>Backups: daily snapshots, 30-day retention</li>
    </ul>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">5. Breach notification</h2>
    <p>In the event of a personal data breach, GenLeadAI will notify the affected Controller within <strong>72 hours</strong> of becoming aware, with description, scope, and mitigation steps.</p>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">6. Controller obligations</h2>
    <ul className="list-disc pl-6 space-y-1">
      <li>Obtain valid consent from every lead before adding them to Aria (especially for WhatsApp outreach).</li>
      <li>Honour STOP / unsubscribe requests immediately (Aria does this automatically).</li>
      <li>Provide leads with a path to request data deletion under DPDP — Aria provides a Delete Personal Data button on every lead.</li>
    </ul>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">7. Audit rights</h2>
    <p>Controllers may request the export of their audit log at any time via Settings → Security → Export Audit Log. GenLeadAI will provide reasonable cooperation with any DPDP enforcement audit.</p>

    <h2 className="text-xl font-bold text-white mt-6 mb-2">8. Data return / deletion on termination</h2>
    <p>On subscription termination, the client may export their data within 30 days. After 90 days, all lead and conversation data is permanently deleted. Invoices retained 7 years per Indian tax law.</p>
  </LegalShell>
);
