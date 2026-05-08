import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { UserCircle, Crown, ShieldCheck } from '@phosphor-icons/react';
import { ptApi, PageHeader, EmptyState } from '../shared';

const ROLE_META = {
  admin:             { label: 'Admin',                  desc: 'Manage integrations, users, scoring rules', color: '#7C35DC', icon: ShieldCheck },
  pietential_owner:  { label: 'Pietential Owner (John)', desc: 'View hot/engaged leads, mark personal follow-up', color: '#C044E0', icon: Crown },
  content_vista:     { label: 'Content Vista Operator',  desc: 'View leads, add notes, manage tasks',     color: '#F59E0B', icon: UserCircle },
  sales_rep:         { label: 'Sales Rep (legacy)',      desc: 'Same as Content Vista Operator',           color: '#475569', icon: UserCircle },
  viewer:            { label: 'Viewer',                  desc: 'Read-only access to dashboard + reports', color: '#94A3B8', icon: UserCircle },
};

const PtTeam = () => {
  const [members, setMembers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [perms, setPerms] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [t, p] = await Promise.all([
        ptApi.get('/api/pt/team'),
        ptApi.get('/api/pt/me/permissions'),
      ]);
      setMembers(t.data.members || []);
      setRoles(t.data.available_roles || []);
      setPerms(p.data);
    } catch (err) {
      if (err.response?.status === 403) toast.error('Admin access only');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const updateRole = async (email, role) => {
    try {
      await ptApi.patch('/api/pt/team/role', { email, role });
      toast.success(`Role updated to ${role}`);
      load();
    } catch (err) { toast.error(err.response?.data?.detail || 'Could not update'); }
  };

  if (loading) return <div className="text-sm text-[#64748B]">Loading…</div>;

  return (
    <div data-testid="pt-team-page">
      <PageHeader title="Team & Roles" subtitle="Manage who can do what across Aria for Pietential." />

      {!perms?.can_admin && (
        <div className="bg-[#FEF3C7] border border-[#F59E0B]/30 rounded-lg p-3 text-sm text-[#92400E] mb-4" data-testid="pt-team-nonadmin-notice">
          You're viewing this as <strong>{perms?.role || 'viewer'}</strong>. Only admins can change roles.
        </div>
      )}

      {/* Role legend */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-6" data-testid="pt-team-role-legend">
        {['admin', 'pietential_owner', 'content_vista', 'viewer'].map(r => {
          const m = ROLE_META[r];
          const Icon = m.icon;
          return (
            <div key={r} className="bg-white border border-[#E2E8F0] rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1.5">
                <div className="w-7 h-7 rounded-md flex items-center justify-center" style={{ background: `${m.color}14`, color: m.color }}>
                  <Icon size={14} weight="duotone" />
                </div>
                <span className="text-sm font-bold text-[#0F172A]">{m.label}</span>
              </div>
              <div className="text-xs text-[#64748B]">{m.desc}</div>
            </div>
          );
        })}
      </div>

      {members.length === 0 ? (
        <EmptyState title="No team members yet" message="Use Sign Up to add new operators." />
      ) : (
        <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden" data-testid="pt-team-table">
          <table className="w-full text-sm">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {['Member', 'Email', 'Role', 'Action'].map(h => <th key={h} className="px-4 py-2 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {members.map(m => {
                const meta = ROLE_META[m.role] || ROLE_META.viewer;
                const Icon = meta.icon;
                return (
                  <tr key={m.email} className="border-b border-[#F1F5F9] last:border-0" data-testid={`pt-team-${m.email.replace(/[@.]/g, '-')}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <img src={m.avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(m.full_name || m.email)}&background=7C35DC&color=fff`} alt="" className="w-7 h-7 rounded-full" />
                        <span className="font-semibold text-[#0F172A]">{m.full_name || '—'}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-[#475569]">{m.email}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-[0.12em]"
                        style={{ color: meta.color, background: `${meta.color}14`, border: `1px solid ${meta.color}33` }}>
                        <Icon size={11} weight="bold" /> {meta.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {perms?.can_admin ? (
                        <select value={m.role} onChange={(e) => updateRole(m.email, e.target.value)}
                          data-testid={`pt-team-role-select-${m.email.replace(/[@.]/g, '-')}`}
                          className="text-xs border border-[#E2E8F0] rounded-md px-2 py-1">
                          {roles.map(r => <option key={r} value={r}>{ROLE_META[r]?.label || r}</option>)}
                        </select>
                      ) : (
                        <span className="text-xs text-[#94A3B8]">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default PtTeam;
