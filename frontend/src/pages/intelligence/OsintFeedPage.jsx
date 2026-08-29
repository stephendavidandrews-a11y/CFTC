import React, { useState, useEffect, useCallback } from "react";
import theme from "../../styles/theme";
import { titleStyle, subtitleStyle, inputStyle, btnPrimary } from "../../styles/pageStyles";
import { useToastContext } from "../../contexts/ToastContext";
import { timeAgo } from "../../utils/dateUtils";
import {
  listOsintItems,
  getOsintTopics,
  setOsintItemRead,
  setOsintItemStarred,
  markAllOsintRead,
  listOsintSources,
  createOsintSource,
  updateOsintSource,
  deleteOsintSource,
  refreshOsint,
} from "../../api/ai";

const PAGE_SIZE = 50;

// Topic chip accents (theme tokens only)
const TOPIC_ACCENTS = {
  china: theme.accent.red,
  taiwan: theme.accent.teal,
  semiconductors: theme.accent.yellow,
  ai: theme.accent.purple,
};

const CATEGORY_LABELS = {
  news: "News",
  analysis: "Analysis",
  think_tank: "Think Tank",
  aggregator: "Aggregator",
  government: "Government",
};

/** Backend stores naive UTC timestamps; mark them as UTC before parsing. */
function asUtc(ts) {
  if (!ts || ts.length <= 10 || ts.endsWith("Z") || ts.includes("+")) return ts;
  return ts + "Z";
}

function TopicChip({ label, accent, count, active, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 7,
        padding: "6px 14px", borderRadius: 16, fontSize: 13, fontWeight: 600,
        cursor: "pointer", transition: "all 0.15s ease",
        background: active ? `${accent}22` : theme.bg.card,
        color: active ? accent : theme.text.muted,
        border: `1px solid ${active ? accent : theme.border.default}`,
      }}
    >
      <span style={{ width: 8, height: 8, borderRadius: 4, background: accent, opacity: active ? 1 : 0.5 }} />
      {label}
      {count > 0 && (
        <span style={{ fontSize: 11, fontWeight: 700, color: active ? accent : theme.text.dim }}>{count}</span>
      )}
    </button>
  );
}

function TopicTag({ slug }) {
  const accent = TOPIC_ACCENTS[slug] || theme.accent.blue;
  const labels = { china: "China", taiwan: "Taiwan", semiconductors: "Semis", ai: "AI" };
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 8,
      background: `${accent}1e`, color: accent, textTransform: "uppercase",
      letterSpacing: "0.04em",
    }}>
      {labels[slug] || slug}
    </span>
  );
}

function FeedItem({ item, onOpen, onToggleStar }) {
  const isUnread = !item.is_read;
  return (
    <div style={{
      background: theme.bg.card,
      border: `1px solid ${theme.border.default}`,
      borderLeft: `3px solid ${isUnread ? theme.accent.blue : theme.border.default}`,
      borderRadius: theme.card.radius, padding: "14px 18px", marginBottom: 10,
      opacity: isUnread ? 1 : 0.75,
    }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 6, flexWrap: "wrap" }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: theme.feed.news.accent }}>
          {item.source_name}
        </span>
        <span style={{ fontSize: 11, color: theme.text.faint }}>
          {timeAgo(asUtc(item.published_at || item.fetched_at))}
        </span>
        {item.author && (
          <span style={{ fontSize: 11, color: theme.text.dim }}>{item.author}</span>
        )}
        <span style={{ flex: 1 }} />
        {(item.topics || []).map((t) => <TopicTag key={t} slug={t} />)}
        <button
          onClick={() => onToggleStar(item)}
          title={item.is_starred ? "Unstar" : "Star"}
          style={{
            background: "transparent", border: "none", cursor: "pointer",
            fontSize: 15, lineHeight: 1, padding: "0 2px",
            color: item.is_starred ? theme.accent.yellow : theme.text.ghost,
          }}
        >
          {item.is_starred ? "★" : "☆"}
        </button>
      </div>
      <a
        href={item.url || "#"}
        target="_blank"
        rel="noopener noreferrer"
        onClick={() => onOpen(item)}
        style={{
          display: "block", fontSize: 14.5, fontWeight: isUnread ? 600 : 500,
          color: isUnread ? theme.text.primary : theme.text.muted,
          textDecoration: "none", marginBottom: item.summary ? 5 : 0,
        }}
      >
        {item.title}
      </a>
      {item.summary && (
        <div style={{ fontSize: 12.5, color: theme.text.dim, lineHeight: 1.5 }}>
          {item.summary}
        </div>
      )}
    </div>
  );
}

function SourceRow({ source, onToggle, onDelete, onRefreshOne, busy }) {
  const statusColor = source.last_status === "error"
    ? theme.accent.red
    : source.last_status === "ok" ? theme.accent.green : theme.text.faint;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12, padding: "9px 12px",
      borderBottom: `1px solid ${theme.border.subtle}`, fontSize: 12.5,
    }}>
      <span
        title={source.last_error || source.last_status || "never fetched"}
        style={{ width: 8, height: 8, borderRadius: 4, background: statusColor, flexShrink: 0 }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ color: source.enabled ? theme.text.secondary : theme.text.faint, fontWeight: 600 }}>
          {source.name}
          <span style={{ fontWeight: 400, color: theme.text.faint, marginLeft: 8, fontSize: 11 }}>
            {CATEGORY_LABELS[source.category] || source.category} {"·"} {source.item_count} items
          </span>
        </div>
        <div style={{
          color: theme.text.ghost, fontSize: 10.5, whiteSpace: "nowrap",
          overflow: "hidden", textOverflow: "ellipsis",
        }}>
          {source.url}
        </div>
      </div>
      <div style={{ display: "flex", gap: 4 }}>
        {(source.default_topics || []).map((t) => <TopicTag key={t} slug={t} />)}
      </div>
      <button
        onClick={() => onRefreshOne(source)}
        disabled={busy}
        title="Fetch this source now"
        style={{
          background: "transparent", border: `1px solid ${theme.border.default}`,
          color: theme.text.dim, borderRadius: 5, padding: "3px 9px",
          fontSize: 11, cursor: busy ? "wait" : "pointer",
        }}
      >
        Fetch
      </button>
      <button
        onClick={() => onToggle(source)}
        style={{
          background: source.enabled ? "rgba(34,197,94,0.12)" : "transparent",
          border: `1px solid ${source.enabled ? theme.accent.green : theme.border.default}`,
          color: source.enabled ? theme.accent.greenLight : theme.text.faint,
          borderRadius: 5, padding: "3px 9px", fontSize: 11, cursor: "pointer",
        }}
      >
        {source.enabled ? "On" : "Off"}
      </button>
      <button
        onClick={() => onDelete(source)}
        title="Delete source and its items"
        style={{
          background: "transparent", border: `1px solid ${theme.border.default}`,
          color: theme.accent.redLight, borderRadius: 5, padding: "3px 9px",
          fontSize: 11, cursor: "pointer",
        }}
      >
        Delete
      </button>
    </div>
  );
}

function AddSourceForm({ onAdd }) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [topics, setTopics] = useState([]);
  const toggleTopic = (slug) =>
    setTopics((prev) => prev.includes(slug) ? prev.filter((t) => t !== slug) : [...prev, slug]);
  const submit = () => {
    if (!name.trim() || !url.trim()) return;
    onAdd({ name: name.trim(), url: url.trim(), category: "news", default_topics: topics });
    setName("");
    setUrl("");
    setTopics([]);
  };
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center", padding: 12, flexWrap: "wrap" }}>
      <input
        style={{ ...inputStyle, minWidth: 160 }}
        placeholder="Source name"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <input
        style={{ ...inputStyle, flex: 1, minWidth: 220 }}
        placeholder="RSS/Atom feed URL (https://...)"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
      />
      {Object.keys(TOPIC_ACCENTS).map((slug) => (
        <label key={slug} style={{
          display: "flex", alignItems: "center", gap: 4, fontSize: 11,
          color: topics.includes(slug) ? TOPIC_ACCENTS[slug] : theme.text.dim, cursor: "pointer",
        }}>
          <input type="checkbox" checked={topics.includes(slug)} onChange={() => toggleTopic(slug)} />
          {slug}
        </label>
      ))}
      <button style={{ ...btnPrimary, padding: "7px 14px" }} onClick={submit}>Add source</button>
    </div>
  );
}

export default function OsintFeedPage() {
  const { success: toastSuccess, error: toastError } = useToastContext();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [topicCounts, setTopicCounts] = useState(null);
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showSources, setShowSources] = useState(false);

  // Filters
  const [topic, setTopic] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [starredOnly, setStarredOnly] = useState(false);
  const [offset, setOffset] = useState(0);

  const buildParams = useCallback((off) => {
    const params = { limit: PAGE_SIZE, offset: off };
    if (topic) params.topic = topic;
    if (sourceId) params.source_id = sourceId;
    if (query) params.q = query;
    if (unreadOnly) params.unread_only = true;
    if (starredOnly) params.starred_only = true;
    return params;
  }, [topic, sourceId, query, unreadOnly, starredOnly]);

  const fetchItems = useCallback(async (off = 0, append = false) => {
    setLoading(true);
    try {
      const data = await listOsintItems(buildParams(off));
      setItems((prev) => (append ? [...prev, ...data.items] : data.items));
      setTotal(data.total);
      setOffset(off);
    } catch (e) {
      toastError("Failed to load feed: " + e.message);
    } finally {
      setLoading(false);
    }
  }, [buildParams, toastError]);

  const fetchMeta = useCallback(async () => {
    try {
      const [topicsData, sourcesData] = await Promise.all([getOsintTopics(), listOsintSources()]);
      setTopicCounts(topicsData);
      setSources(sourcesData.sources);
    } catch {
      // counts are cosmetic; the items call surfaces real errors
    }
  }, []);

  useEffect(() => { fetchItems(0); }, [fetchItems]);
  useEffect(() => { fetchMeta(); }, [fetchMeta]);

  // Debounce search box into the query filter
  useEffect(() => {
    const id = setTimeout(() => setQuery(search.trim()), 350);
    return () => clearTimeout(id);
  }, [search]);

  const handleRefresh = async (oneSourceId = null) => {
    setRefreshing(true);
    try {
      const result = await refreshOsint(oneSourceId);
      toastSuccess(
        `Refreshed ${result.sources_checked} source${result.sources_checked === 1 ? "" : "s"}: ` +
        `${result.new_items} new item${result.new_items === 1 ? "" : "s"}` +
        (result.errors ? `, ${result.errors} failed` : "")
      );
      await Promise.all([fetchItems(0), fetchMeta()]);
    } catch (e) {
      toastError("Refresh failed: " + e.message);
    } finally {
      setRefreshing(false);
    }
  };

  const handleOpen = async (item) => {
    if (item.is_read) return;
    setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, is_read: 1 } : i)));
    try {
      await setOsintItemRead(item.id, true);
      fetchMeta();
    } catch {
      // non-critical
    }
  };

  const handleToggleStar = async (item) => {
    const next = !item.is_starred;
    setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, is_starred: next ? 1 : 0 } : i)));
    try {
      await setOsintItemStarred(item.id, next);
    } catch (e) {
      toastError("Failed to update star: " + e.message);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      const params = {};
      if (topic) params.topic = topic;
      if (sourceId) params.source_id = sourceId;
      const result = await markAllOsintRead(params);
      toastSuccess(`Marked ${result.marked_read} items read`);
      await Promise.all([fetchItems(0), fetchMeta()]);
    } catch (e) {
      toastError("Failed: " + e.message);
    }
  };

  const handleToggleSource = async (source) => {
    try {
      await updateOsintSource(source.id, { enabled: !source.enabled });
      fetchMeta();
    } catch (e) {
      toastError("Failed to update source: " + e.message);
    }
  };

  const handleDeleteSource = async (source) => {
    if (!window.confirm(`Delete "${source.name}" and all its items?`)) return;
    try {
      await deleteOsintSource(source.id);
      toastSuccess("Source deleted");
      await Promise.all([fetchItems(0), fetchMeta()]);
    } catch (e) {
      toastError("Failed to delete source: " + e.message);
    }
  };

  const handleAddSource = async (data) => {
    try {
      await createOsintSource(data);
      toastSuccess(`Added "${data.name}"`);
      fetchMeta();
    } catch (e) {
      toastError("Failed to add source: " + e.message);
    }
  };

  const allCounts = topicCounts?.all || { total: 0, unread: 0 };
  const byTopic = {};
  (topicCounts?.topics || []).forEach((t) => { byTopic[t.slug] = t; });

  return (
    <div style={{ padding: 28, maxWidth: 880 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 260 }}>
          <div style={titleStyle}>OSINT Feed</div>
          <div style={subtitleStyle}>
            Open-source monitoring: China, Taiwan, semiconductors, and AI
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={handleMarkAllRead}
            style={{
              ...btnPrimary, background: "transparent",
              border: `1px solid ${theme.border.default}`, color: theme.text.muted,
            }}
          >
            Mark all read
          </button>
          <button
            onClick={() => handleRefresh()}
            disabled={refreshing}
            style={{ ...btnPrimary, opacity: refreshing ? 0.6 : 1, cursor: refreshing ? "wait" : "pointer" }}
          >
            {refreshing ? "Refreshing..." : "Refresh feeds"}
          </button>
        </div>
      </div>

      {/* Topic chips */}
      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        <TopicChip
          label="All"
          accent={theme.accent.blue}
          count={allCounts.unread}
          active={!topic}
          onClick={() => setTopic("")}
        />
        {Object.entries(TOPIC_ACCENTS).map(([slug, accent]) => (
          <TopicChip
            key={slug}
            label={byTopic[slug]?.label || slug}
            accent={accent}
            count={byTopic[slug]?.unread || 0}
            active={topic === slug}
            onClick={() => setTopic(topic === slug ? "" : slug)}
          />
        ))}
      </div>

      {/* Filter bar */}
      <div style={{ display: "flex", gap: 10, marginBottom: 18, alignItems: "center", flexWrap: "wrap" }}>
        <input
          style={{ ...inputStyle, flex: 1, minWidth: 180 }}
          placeholder="Search titles and summaries..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          style={{ ...inputStyle, minWidth: 170 }}
          value={sourceId}
          onChange={(e) => setSourceId(e.target.value)}
        >
          <option value="">All sources</option>
          {sources.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: theme.text.dim, cursor: "pointer" }}>
          <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} />
          Unread
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: theme.text.dim, cursor: "pointer" }}>
          <input type="checkbox" checked={starredOnly} onChange={(e) => setStarredOnly(e.target.checked)} />
          Starred
        </label>
        <button
          onClick={() => setShowSources(!showSources)}
          style={{
            background: "transparent", border: `1px solid ${theme.border.default}`,
            color: showSources ? theme.accent.blueLight : theme.text.dim,
            borderRadius: 6, padding: "7px 12px", fontSize: 12, cursor: "pointer",
          }}
        >
          Sources ({sources.length})
        </button>
      </div>

      {/* Sources manager */}
      {showSources && (
        <div style={{
          background: theme.bg.card, border: `1px solid ${theme.border.default}`,
          borderRadius: theme.card.radius, marginBottom: 18, overflow: "hidden",
        }}>
          <div style={{
            padding: "10px 12px", borderBottom: `1px solid ${theme.border.subtle}`,
            fontSize: 12, fontWeight: 700, color: theme.text.muted,
            textTransform: "uppercase", letterSpacing: "0.05em",
          }}>
            Feed Sources
          </div>
          {sources.map((s) => (
            <SourceRow
              key={s.id}
              source={s}
              busy={refreshing}
              onToggle={handleToggleSource}
              onDelete={handleDeleteSource}
              onRefreshOne={(src) => handleRefresh(src.id)}
            />
          ))}
          <AddSourceForm onAdd={handleAddSource} />
        </div>
      )}

      {/* Items */}
      {loading && items.length === 0 ? (
        <div style={{ color: theme.text.faint, fontSize: 13, padding: 30, textAlign: "center" }}>
          Loading feed...
        </div>
      ) : items.length === 0 ? (
        <div style={{
          background: theme.bg.card, border: `1px solid ${theme.border.default}`,
          borderRadius: theme.card.radius, padding: 40, textAlign: "center",
          color: theme.text.dim, fontSize: 13,
        }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: theme.text.muted, marginBottom: 6 }}>
            No items yet
          </div>
          Click "Refresh feeds" to pull the latest from your sources.
          The feed also updates automatically in the background.
        </div>
      ) : (
        <>
          {items.map((item) => (
            <FeedItem key={item.id} item={item} onOpen={handleOpen} onToggleStar={handleToggleStar} />
          ))}
          {items.length < total && (
            <button
              onClick={() => fetchItems(offset + PAGE_SIZE, true)}
              disabled={loading}
              style={{
                display: "block", width: "100%", padding: "10px 0", marginTop: 4,
                background: theme.bg.card, border: `1px solid ${theme.border.default}`,
                borderRadius: theme.card.radius, color: theme.text.muted,
                fontSize: 13, fontWeight: 600, cursor: "pointer",
              }}
            >
              {loading ? "Loading..." : `Load more (${total - items.length} remaining)`}
            </button>
          )}
        </>
      )}
    </div>
  );
}
