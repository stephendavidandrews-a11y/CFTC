import React from 'react';

export default function QuickText({ phone, name }) {
  if (!phone) return null;

  const cleanPhone = phone.replace(/[^\d+]/g, '');
  const smsLink = `sms:${cleanPhone}`;

  return (
    <a href={smsLink} className="quick-text-btn" title={`Text ${name || ''}`}>
      {'\u{1F4AC}'} Quick Text
    </a>
  );
}
