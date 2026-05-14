/**
 * AvatarPicker — reusable component for uploading / changing / removing
 * a user's profile picture.
 *
 * Flow
 * ----
 *   1. User clicks the avatar (or the camera badge overlay).
 *   2. Native file picker opens (image/*).
 *   3. We draw the image onto an off-screen <canvas>, center-crop to a
 *      square, downscale to 256×256, export JPEG @ q=0.85 → data URL.
 *   4. PUT to /api/users/me/avatar (or /{email}/avatar if `email` prop
 *      is set and the current user has owner/admin rights).
 *   5. `onUpdated(newAvatarUrl)` fires so the parent can refresh its
 *      cached view.
 *
 * Falls back to a clean initials avatar (gradient + first letter) when
 * no avatar_url is set. Includes a hover-revealed "Remove" link that
 * clears the avatar on the server.
 */
import React, { useRef, useState } from 'react';
import { toast } from 'sonner';
import api from '../config/api';
import { Camera, Trash, Spinner } from '@phosphor-icons/react';

const SIZE = 256;
const Q = 0.85;
const MAX_INPUT_BYTES = 10 * 1024 * 1024;  // 10MB pre-resize cap

const initials = (name = '', email = '') => {
  const s = (name || email || '?').trim();
  const parts = s.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return s.slice(0, 2).toUpperCase();
};

// Stable color per email so two members with similar initials don't clash.
const tintFor = (key = '') => {
  const colors = ['#7C35DC', '#0055FF', '#C044E0', '#D97706', '#16A34A', '#DC2626', '#5B28D4', '#0F766E'];
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return colors[h % colors.length];
};

const resizeToDataUrl = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Could not read file'));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error('Could not decode image'));
      img.onload = () => {
        try {
          // Center-crop square
          const side = Math.min(img.width, img.height);
          const sx = (img.width - side) / 2;
          const sy = (img.height - side) / 2;
          const canvas = document.createElement('canvas');
          canvas.width = SIZE;
          canvas.height = SIZE;
          const ctx = canvas.getContext('2d');
          ctx.imageSmoothingEnabled = true;
          ctx.imageSmoothingQuality = 'high';
          ctx.drawImage(img, sx, sy, side, side, 0, 0, SIZE, SIZE);
          resolve(canvas.toDataURL('image/jpeg', Q));
        } catch (e) { reject(e); }
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });

const AvatarPicker = ({
  user,              // { email, full_name, avatar_url }
  email = null,      // when set, updates this email's avatar (admin-only)
  editable = true,
  size = 64,
  onUpdated,
  showRemove = true,
  className = '',
  testidPrefix = 'avatar',
}) => {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [override, setOverride] = useState(null);  // optimistic preview

  const targetEmail = email || user?.email;
  const avatar = override !== null ? override : (user?.avatar_url || null);
  const dim = { width: size, height: size, fontSize: Math.max(11, size * 0.36) };

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (e.target) e.target.value = '';  // allow re-picking same file
    if (!file) return;
    if (!file.type.startsWith('image/')) { toast.error('Please choose an image file.'); return; }
    if (file.size > MAX_INPUT_BYTES) { toast.error('Image too big — max 10MB.'); return; }
    setBusy(true);
    try {
      const dataUrl = await resizeToDataUrl(file);
      // Optimistic preview
      setOverride(dataUrl);
      const path = email ? `/api/users/${encodeURIComponent(email)}/avatar` : '/api/users/me/avatar';
      const { data } = await api.put(path, { data_url: dataUrl });
      const next = data?.user?.avatar_url || dataUrl;
      setOverride(null);
      onUpdated && onUpdated(next, data?.user);
      // Keep cached `user` in localStorage in sync when updating self
      if (!email) {
        try {
          const u = JSON.parse(localStorage.getItem('user') || '{}');
          if (u?.email) { u.avatar_url = next; localStorage.setItem('user', JSON.stringify(u)); }
        } catch { /* ignore */ }
        // Broadcast so the sidebar / topbar avatar can refresh without a page reload.
        window.dispatchEvent(new CustomEvent('aria:user-avatar-updated', { detail: { avatar_url: next } }));
      }
      toast.success('Profile picture updated');
    } catch (err) {
      setOverride(null);
      toast.error(err?.response?.data?.detail || err?.message || 'Upload failed');
    } finally {
      setBusy(false);
    }
  };

  const handleRemove = async (e) => {
    e?.stopPropagation?.();
    if (!avatar) return;
    setBusy(true);
    try {
      const path = email ? `/api/users/${encodeURIComponent(email)}/avatar` : '/api/users/me/avatar';
      const { data } = await api.delete(path);
      setOverride(null);
      onUpdated && onUpdated(null, data?.user);
      if (!email) {
        try {
          const u = JSON.parse(localStorage.getItem('user') || '{}');
          if (u?.email) { u.avatar_url = null; localStorage.setItem('user', JSON.stringify(u)); }
        } catch { /* ignore */ }
        window.dispatchEvent(new CustomEvent('aria:user-avatar-updated', { detail: { avatar_url: null } }));
      }
      toast.success('Profile picture removed');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not remove');
    } finally {
      setBusy(false);
    }
  };

  const tint = tintFor(targetEmail || user?.full_name || '');
  const isUiAvatarsFallback = avatar && typeof avatar === 'string' && avatar.includes('ui-avatars.com');

  return (
    <div className={`relative inline-block group ${className}`} data-testid={`${testidPrefix}-root`}>
      <button
        type="button"
        disabled={!editable || busy}
        onClick={() => editable && inputRef.current?.click()}
        className={`relative overflow-hidden rounded-full border-2 border-white transition-all ${editable ? 'cursor-pointer hover:ring-2 hover:ring-[#7C35DC]/40' : 'cursor-default'}`}
        style={{ ...dim, background: tint, boxShadow: '0 4px 12px rgba(26,10,46,0.10)' }}
        data-testid={`${testidPrefix}-trigger`}
        aria-label={editable ? 'Change profile picture' : 'Profile picture'}
      >
        {avatar && !isUiAvatarsFallback ? (
          <img src={avatar} alt={user?.full_name || targetEmail} className="w-full h-full object-cover" data-testid={`${testidPrefix}-img`} />
        ) : (
          <span className="absolute inset-0 flex items-center justify-center text-white font-extrabold" style={{ fontSize: dim.fontSize, fontFamily: 'Plus Jakarta Sans' }} data-testid={`${testidPrefix}-initials`}>
            {initials(user?.full_name, targetEmail)}
          </span>
        )}
        {editable && !busy && (
          <span className="absolute bottom-0 right-0 w-1/3 h-1/3 min-w-[20px] min-h-[20px] bg-white rounded-tl-md flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity" data-testid={`${testidPrefix}-camera-badge`}>
            <Camera size={Math.max(10, size * 0.18)} weight="fill" className="text-[#7C35DC]" />
          </span>
        )}
        {busy && (
          <span className="absolute inset-0 bg-black/40 flex items-center justify-center">
            <Spinner size={Math.max(14, size * 0.3)} weight="bold" className="text-white animate-spin" />
          </span>
        )}
      </button>

      {showRemove && editable && avatar && !isUiAvatarsFallback && !busy && (
        <button
          type="button"
          onClick={handleRemove}
          data-testid={`${testidPrefix}-remove`}
          title="Remove profile picture"
          className="absolute -top-1.5 -right-1.5 w-6 h-6 rounded-full bg-white border border-[#E8E0F5] shadow-sm flex items-center justify-center text-[#DC2626] hover:bg-[#FEE2E2] opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <Trash size={11} weight="fill" />
        </button>
      )}

      {editable && (
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={handleFile}
          className="hidden"
          data-testid={`${testidPrefix}-file-input`}
        />
      )}
    </div>
  );
};

export default AvatarPicker;
