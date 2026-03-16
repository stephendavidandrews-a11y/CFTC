import React, { useState, useEffect } from "react";
import Pulse from "./Pulse";
import theme from "../../styles/theme";

const DEMO_FEED = [
  { time: "2 min ago", type: "tweet", source: "@CFTCChairman", text: "Excited to announce progress on our digital assets framework. The PWG report is ahead of schedule.", icon: "\ud835\udd4f" },
  { time: "18 min ago", type: "news", source: "Reuters", text: "SEC and CFTC to hold joint hearing on crypto custody rules next month", icon: "\u25c6" },
  { time: "34 min ago", type: "fr", source: "Federal Register", text: "CFTC-2025-0005: Digital Asset Clearing Amendments \u2014 12 new comments received", icon: "\u2b22" },
  { time: "1 hr ago", type: "tweet", source: "@SenLummis", text: "Bipartisan stablecoin bill moves to markup next week. Strong support from Treasury and CFTC.", icon: "\ud835\udd4f" },
  { time: "1.5 hr ago", type: "news", source: "CoinDesk", text: "Kalshi seeks to expand political event contracts after favorable CFTC guidance", icon: "\u25c6" },
  { time: "2 hr ago", type: "regulatory", source: "SEC", text: "Staff Accounting Bulletin 122 rescission \u2014 crypto custody treatment revised", icon: "\u2295" },
  { time: "3 hr ago", type: "tweet", source: "@HesterPeirce", text: "Tokenized collateral is the next frontier. Looking forward to CFTC's proposed framework.", icon: "\ud835\udd4f" },
  { time: "4 hr ago", type: "fr", source: "Federal Register", text: "OCC issues interpretive letter on national bank authority for stablecoin reserves", icon: "\u2b22" },
  { time: "5 hr ago", type: "news", source: "Bloomberg", text: "Trump crypto working group targets July deadline for comprehensive regulatory framework", icon: "\u25c6" },
  { time: "6 hr ago", type: "regulatory", source: "Treasury", text: "FinCEN proposed rule on DeFi broker definition \u2014 comment period opens March 1", icon: "\u2295" },
];

export default function LiveFeed({ items: externalItems }) {
  const items = externalItems || DEMO_FEED;
  const [flash, setFlash] = useState(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setFlash(0);
      setTimeout(() => setFlash(null), 2000);
    }, 12000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{
      background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`,
      padding: 20, height: "100%", display: "flex", flexDirection: "column",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <Pulse color={theme.accent.green} />
        <h3 style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
          Live Intelligence Feed
        </h3>
        <span style={{ fontSize: 10, color: theme.text.faint, marginLeft: "auto" }}>Auto-updating</span>
      </div>
      <div style={{ flex: 1, overflowY: "auto" }}>
        {items.map((item, i) => {
          const fc = theme.feed[item.type] || theme.feed.news;
          const isFlash = flash === i;
          return (
            <div key={i} style={{
              padding: "12px 14px", marginBottom: 6, borderRadius: 8,
              background: isFlash ? fc.bg : "transparent",
              borderLeft: `3px solid ${isFlash ? fc.accent : "transparent"}`,
              transition: "all 0.5s ease", cursor: "pointer",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 12, color: fc.accent, fontWeight: 700 }}>{item.icon}</span>
                <span style={{ fontSize: 11, fontWeight: 600, color: fc.accent }}>{item.source}</span>
                <span style={{ fontSize: 10, color: theme.text.faint, marginLeft: "auto" }}>{item.time}</span>
              </div>
              <div style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.5 }}>{item.text}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
