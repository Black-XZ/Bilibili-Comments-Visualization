import { useState, useEffect } from 'react';

export interface SummaryData {
  video_title: string;
  bvid: string;
  duration_sec: number;
  duration_min: number;
  danmaku_count: number;
  root_comment_count: number;
  reply_count: number;
  total_comment_count: number;
  avg_reply_per_root: number;
  max_likes: number;
  dm_top_words: string[];
  cmt_top_words: string[];
  sentiment: {
    danmaku: { positive: number; neutral: number; negative: number; avg_score: number };
    comment: { positive: number; neutral: number; negative: number; avg_score: number };
  };
}

export interface TimeDataPoint {
  label: string;
  value: number;
}

export interface KeywordItem {
  word: string;
  count: number;
}

export interface TopComment {
  content: string;
  likes: number;
  replies: number;
  user: string;
  level: number;
  sentiment: string;
}

export interface DashboardData {
  summary: SummaryData;
  dm_time: { labels: string[]; values: number[] };
  sentiment: SummaryData['sentiment'];
  sentiment_hist: { danmaku: { bins: number[]; counts: number[] } };
  keywords: { danmaku: KeywordItem[]; comment: KeywordItem[] };
  level_dist: { labels: string[]; values: number[] };
  heatmap: { labels: string[]; values: number[] };
  dm_type: { labels: string[]; values: number[] };
  top_comments: TopComment[];
}

export function useDashboardData() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/dashboard_data.json')
      .then((res) => res.json())
      .then((json: DashboardData) => {
        setData(json);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return { data, loading };
}
