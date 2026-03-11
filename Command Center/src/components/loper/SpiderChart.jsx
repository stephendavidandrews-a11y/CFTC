import React from "react";
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Radar, ResponsiveContainer, Tooltip,
} from "recharts";
import theme from "../../styles/theme";

/**
 * Radar/spider chart for dimension scores.
 *
 * Props:
 *  dimensions: [{ label: string, value: number (0-10) }]
 *  size: number (default 300)
 */
export default function SpiderChart({ dimensions = [], size = 300 }) {
  if (!dimensions || dimensions.length === 0) return null;

  const data = dimensions.map((d) => ({
    subject: d.label,
    value: d.value != null ? d.value : 0,
    fullMark: 10,
  }));

  // Color by max value
  const maxVal = Math.max(...data.map((d) => d.value));
  let fillColor, strokeColor;
  if (maxVal >= 7) { fillColor = "rgba(239,68,68,0.2)"; strokeColor = "#ef4444"; }
  else if (maxVal >= 5) { fillColor = "rgba(245,158,11,0.2)"; strokeColor = "#f59e0b"; }
  else if (maxVal >= 3) { fillColor = "rgba(59,130,246,0.2)"; strokeColor = "#3b82f6"; }
  else { fillColor = "rgba(71,85,105,0.2)"; strokeColor = "#475569"; }

  return (
    <ResponsiveContainer width="100%" height={size}>
      <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
        <PolarGrid stroke={theme.border.subtle} />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fontSize: 11, fill: theme.text.muted }}
        />
        <PolarRadiusAxis
          domain={[0, 10]}
          tick={{ fontSize: 9, fill: theme.text.ghost }}
          tickCount={6}
        />
        <Radar
          name="Score"
          dataKey="value"
          stroke={strokeColor}
          fill={fillColor}
          strokeWidth={2}
        />
        <Tooltip
          contentStyle={{
            background: "#1e293b",
            border: `1px solid ${theme.border.default}`,
            borderRadius: 6,
            fontSize: 12,
            color: theme.text.secondary,
          }}
          formatter={(v) => [v.toFixed(1), "Score"]}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
