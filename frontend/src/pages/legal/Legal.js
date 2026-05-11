/**
 * Legal — /privacy, /terms, /dpa pages.
 *
 * Self-contained, GenLeadAI branded, DPDP Act 2023 compliant where relevant.
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ShieldCheck, Scroll, FileText } from '@phosphor-icons/react';

const LegalShell = ({ title, kind, lastUpdated, children }) => {
  const icons = { privacy: ShieldCheck, terms: Scroll, dpa: FileText };
  const Icon = icons[kind] || ShieldCheck;
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#FAFAFA] to-white" data-testid={`legal-${kind}`}>
      <div className="max-w-3xl mx-auto px-6 py-12">
        <Link to="/" className="inline-flex items-center gap-1.5 text-xs font-bold text-[#7C35DC] hover:text-[#6B28C8] mb-6">
          <ArrowLeft size={12} weight="bold" /> Back to Aria
        </Link>
        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-8 md:p-10" style={{ boxShadow: 'var(--shadow-card)' }}>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-[#F4F0FF] flex items-center justify-center">
              <Icon size={20} weight="duotone" className="text-[#7C35DC]" />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{title}</h1>
              <p className="text-xs text-[#9B8AB0]">Last updated: {lastUpdated}</p>
            </div>
          </div>
          <div className="mt-6 space-y-4 text-sm leading-relaxed text-[#1A0A2E] [&_h2]:text-base [&_h2]:font-extrabold [&_h2]:text-[#1A0A2E] [&_h2]:mt-6 [&_h2]:mb-2 [&_h3]:text-sm [&_h3]:font-bold [&_h3]:text-[#1A0A2E] [&_h3]:mt-4 [&_h3]:mb-1 [&_p]:text-[#5A4A7A] [&_ul]:list-disc [&_ul]:pl-5 [&_ul_li]:text-[#5A4A7A] [&_ul_li]:mb-1">
            {children}
          </div>
        </div>
        <p className="text-[10px] text-[#9B8AB0] text-center mt-6">
          Powered by Aria · GenLeadAI · <a href="mailto:meghaagarwal@genleadai.com" className="underline">meghaagarwal@genleadai.com</a>
        </p>
      </div>
    </div>
  );
};

export const Privacy = () => (
  <LegalShell title="Privacy Policy" kind="privacy" lastUpdated="11 February 2026">
    <p>This Privacy Policy describes how <strong>GenLeadAI</strong> ("we", "us", "Aria") collects, uses, stores, and shares personal data when you use the Aria platform (app.genleadai.com).</p>

    <h2>1. Who we are</h2>
    <p>GenLeadAI operates Aria, an AI-powered WhatsApp Sales PA. We are the <em>Data Processor</em> for personal data uploaded by our customers (workspaces) and the <em>Data Fiduciary</em> for account-holder information you provide to register and use the platform.</p>

    <h2>2. Data we collect</h2>
    <ul>
      <li><strong>Account data:</strong> name, email, password (hashed), workspace name.</li>
      <li><strong>Lead data uploaded by your workspace:</strong> names, phone numbers, email, conversation transcripts, opt-in records.</li>
      <li><strong>Usage data:</strong> IP address, browser type, timestamps of actions.</li>
      <li><strong>Billing data:</strong> processed via Stripe; we never store full card details.</li>
    </ul>

    <h2>3. How we use your data</h2>
    <ul>
      <li>Operate the Aria platform and deliver contracted services.</li>
      <li>Send transactional emails (login, password reset, invoices).</li>
      <li>Improve product reliability and performance.</li>
      <li>Comply with applicable legal obligations.</li>
    </ul>

    <h2>4. Lawful basis (DPDP Act 2023)</h2>
    <p>We process personal data under the lawful bases of <strong>contract performance</strong> (delivering Aria to you), <strong>legitimate interest</strong> (security, fraud prevention), and <strong>consent</strong> (marketing, analytics).</p>

    <h2>5. Your rights as a Data Principal</h2>
    <ul>
      <li>Right to access, correct or update your data.</li>
      <li>Right to erasure (delete your account and all associated data).</li>
      <li>Right to nominate (designate another individual to exercise rights on your behalf).</li>
      <li>Right to grievance redressal — email <a href="mailto:meghaagarwal@genleadai.com" className="text-[#7C35DC] underline">meghaagarwal@genleadai.com</a>.</li>
    </ul>

    <h2>6. Data storage and security</h2>
    <p>Lead data is stored in encrypted-at-rest MongoDB clusters. All third-party API keys (360dialog, CRM tokens, Stripe) are encrypted with Fernet keys stored separately. We use HTTPS for all traffic, rate limiting on authentication, audit logging for sensitive actions, and DPDP-compliant deletion endpoints.</p>

    <h2>7. Sub-processors</h2>
    <ul>
      <li><strong>Anthropic Claude</strong> — natural language understanding (no data retention beyond the API call).</li>
      <li><strong>360dialog</strong> — WhatsApp message delivery.</li>
      <li><strong>Stripe</strong> — payment processing.</li>
      <li><strong>Resend</strong> — transactional email.</li>
      <li><strong>MongoDB Atlas</strong> — primary database hosting.</li>
    </ul>

    <h2>8. Retention</h2>
    <p>Conversation message content is retained for 365 days. Classification logs for 180 days. API usage logs for 90 days. Resolved failed-message logs for 30 days. Workspace data on the whole is retained for the lifetime of your subscription, plus 30 days after cancellation, after which it is fully deleted.</p>

    <h2>9. International transfers</h2>
    <p>Data is primarily processed in India and the EU. Some sub-processors (e.g. Anthropic, Stripe) operate in the United States — adequate contractual safeguards are in place.</p>

    <h2>10. Contact</h2>
    <p>Grievance Officer: <strong>Megha Agarwal</strong> · <a href="mailto:meghaagarwal@genleadai.com" className="text-[#7C35DC] underline">meghaagarwal@genleadai.com</a>. We will respond within 30 days of receiving a request.</p>
  </LegalShell>
);

export const Terms = () => (
  <LegalShell title="Terms of Service" kind="terms" lastUpdated="11 February 2026">
    <p>By signing up to or using the Aria platform you agree to these Terms.</p>

    <h2>1. The service</h2>
    <p>Aria is an AI-powered WhatsApp Sales PA. Plans (DIY, DWY, DFY) differ only in the operator — the underlying tool is identical. All plans begin with a 14-day free trial; no card required.</p>

    <h2>2. Your responsibilities</h2>
    <ul>
      <li><strong>Opt-in compliance:</strong> You are solely responsible for ensuring every lead you contact via Aria has opted in to receive WhatsApp / email communication. Use Aria's opt-in tools to manage consent.</li>
      <li><strong>Accurate workspace info:</strong> Keep your business profile and Aria configuration accurate.</li>
      <li><strong>No prohibited content:</strong> No spam, scams, hate, harassment, sexual content, or illegal services.</li>
      <li><strong>WhatsApp policy:</strong> You must comply with Meta's WhatsApp Business Policy at all times. GenLeadAI is not liable for account bans caused by your messages.</li>
    </ul>

    <h2>3. Fees and trials</h2>
    <p>Plan pricing is displayed at <code>/billing</code>. Trials auto-expire after 14 days and access is locked until you select a plan. Refunds are discretionary and handled case-by-case.</p>

    <h2>4. Acceptable use</h2>
    <p>You will not (a) reverse-engineer Aria; (b) resell or sublicense without written permission; (c) attempt to bypass rate limits or extract data you do not own; (d) use Aria to harass any person.</p>

    <h2>5. Suspension and termination</h2>
    <p>We may suspend or terminate a workspace that violates these Terms or Meta's policies, or that becomes a source of abuse complaints. You may cancel at any time from the billing page.</p>

    <h2>6. Limitation of liability</h2>
    <p>To the maximum extent allowed by law, GenLeadAI's aggregate liability is capped at the fees you paid in the 12 months preceding the claim. Indirect, consequential, or punitive damages are excluded.</p>

    <h2>7. Governing law</h2>
    <p>These Terms are governed by the laws of India. Courts at New Delhi shall have exclusive jurisdiction.</p>

    <h2>8. Changes</h2>
    <p>We may update these Terms with notice via email or in-app banner. Continued use after the effective date constitutes acceptance.</p>

    <h2>9. Contact</h2>
    <p>Questions: <a href="mailto:meghaagarwal@genleadai.com" className="text-[#7C35DC] underline">meghaagarwal@genleadai.com</a></p>
  </LegalShell>
);

export const Dpa = () => (
  <LegalShell title="Data Processing Agreement" kind="dpa" lastUpdated="11 February 2026">
    <p>This Data Processing Agreement ("DPA") is incorporated into the Terms of Service between you (the "Customer", acting as Data Fiduciary) and GenLeadAI (the "Processor"). It governs Aria's processing of personal data on your behalf.</p>

    <h2>1. Scope</h2>
    <p>This DPA applies whenever Aria processes personal data about your leads, contacts or end customers on your instructions.</p>

    <h2>2. Subject matter and duration</h2>
    <p>The duration of processing aligns with your subscription term plus any retention period required by these Terms or applicable law.</p>

    <h2>3. Nature and purpose of processing</h2>
    <ul>
      <li>Storing and organising lead and conversation data inside your workspace.</li>
      <li>Sending automated WhatsApp / email touchpoints on your behalf.</li>
      <li>Running Aria's classification, sentiment, and pipeline-health AI features.</li>
      <li>Generating analytics and reports for your workspace.</li>
    </ul>

    <h2>4. Categories of data</h2>
    <p>Names, phone numbers, email addresses, company affiliation, message content, opt-in status, deal stage and score.</p>

    <h2>5. Processor obligations</h2>
    <ul>
      <li>Process personal data only on your documented instructions.</li>
      <li>Ensure personnel are bound by confidentiality.</li>
      <li>Implement technical and organisational measures: encryption at rest, encrypted secrets vault, RBAC, audit logging, rate limiting, DPDP-compliant deletion.</li>
      <li>Notify you without undue delay of any personal data breach.</li>
      <li>Assist you in fulfilling Data Principal requests (access, correction, erasure).</li>
    </ul>

    <h2>6. Sub-processors</h2>
    <p>The current list is published in our <Link to="/privacy" className="text-[#7C35DC] underline">Privacy Policy § 7</Link>. We will notify you (via in-app banner or email) at least 30 days before adding a new sub-processor.</p>

    <h2>7. International transfers</h2>
    <p>Where personal data is transferred outside India, we rely on contractual safeguards (e.g. Standard Contractual Clauses) with the sub-processor concerned.</p>

    <h2>8. Audit</h2>
    <p>Upon reasonable notice, you may request a written summary of our security controls. On-site audits are available to Enterprise / DFY customers under NDA.</p>

    <h2>9. Return / deletion</h2>
    <p>On termination, we return or delete all personal data within 30 days, unless retention is required by law.</p>

    <h2>10. Contact</h2>
    <p>For DPA matters: <a href="mailto:meghaagarwal@genleadai.com" className="text-[#7C35DC] underline">meghaagarwal@genleadai.com</a></p>
  </LegalShell>
);

const Legal = Privacy;
export const DPA = Dpa;
export default Legal;
