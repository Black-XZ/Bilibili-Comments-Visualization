import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useDashboardData } from '@/hooks/useDashboardData';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar
} from 'recharts';
import {
  MessageSquare, Heart, ThumbsUp, Users, Clock, TrendingUp,
  BarChart3, MessageCircle
} from 'lucide-react';

const COLORS = {
  pink: '#FB7299',
  pinkLight: '#FDCAD4',
  blue: '#00A1D6',
  blueLight: '#B3E5FC',
  green: '#4CAF50',
  greenLight: '#C8E6C9',
  orange: '#FF9800',
  orangeLight: '#FFE0B2',
  purple: '#9C27B0',
  purpleLight: '#E1BEE7',
  red: '#F44336',
  yellow: '#FFC107',
  teal: '#009688'
};

const PIE_COLORS = [COLORS.green, COLORS.yellow, COLORS.red];
const TYPE_COLORS = [COLORS.pink, COLORS.blue, COLORS.green];

function StatCard({ title, value, subtitle, icon: Icon, color }: {
  title: string; value: string | number; subtitle?: string;
  icon: React.ElementType; color: string;
}) {
  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold" style={{ color }}>{value}</p>
            {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
          </div>
          <div className="p-2 rounded-lg" style={{ backgroundColor: color + '18' }}>
            <Icon size={20} style={{ color }} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SentimentBadge({ sentiment }: { sentiment: string }) {
  const config: Record<string, { bg: string; text: string }> = {
    '正面': { bg: COLORS.green + '20', text: COLORS.green },
    '中性': { bg: COLORS.yellow + '20', text: '#B8860B' },
    '负面': { bg: COLORS.red + '20', text: COLORS.red },
  };
  const c = config[sentiment] || config['中性'];
  return (
    <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ backgroundColor: c.bg, color: c.text }}>
      {sentiment}
    </span>
  );
}

export default function Dashboard() {
  const { data, loading } = useDashboardData();

  if (loading || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-4 border-pink-400 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-muted-foreground">加载数据中...</p>
        </div>
      </div>
    );
  }

  const s = data.summary;

  // 转换数据格式
  const dmTimeChart = data.dm_time.labels.map((label, i) => ({
    time: label,
    count: data.dm_time.values[i]
  }));

  const dmSentimentPie = [
    { name: '正面', value: data.sentiment.danmaku.positive },
    { name: '中性', value: data.sentiment.danmaku.neutral },
    { name: '负面', value: data.sentiment.danmaku.negative },
  ];

  const cmtSentimentPie = [
    { name: '正面', value: data.sentiment.comment.positive },
    { name: '中性', value: data.sentiment.comment.neutral },
    { name: '负面', value: data.sentiment.comment.negative },
  ];

  const dmKeywordsChart = data.keywords.danmaku.slice(0, 10).map(k => ({ word: k.word, count: k.count })).reverse();
  const cmtKeywordsChart = data.keywords.comment.slice(0, 10).map(k => ({ word: k.word, count: k.count })).reverse();

  const levelChart = data.level_dist.labels.map((label, i) => ({
    level: `Lv.${label}`,
    count: data.level_dist.values[i]
  }));

  const typeChart = data.dm_type.labels.map((label, i) => ({
    type: label,
    count: data.dm_type.values[i]
  }));

  const heatmapChart = data.heatmap.labels.map((label, i) => ({
    time: label,
    count: data.heatmap.values[i]
  }));

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ backgroundColor: COLORS.pink }}>
              <BarChart3 size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold">B站视频数据分析看板</h1>
              <p className="text-xs text-muted-foreground">{s.video_title} · {s.bvid}</p>
            </div>
          </div>
          <Badge variant="outline" className="text-xs">视频时长 {s.duration_min} 分钟</Badge>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Stat Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard title="弹幕总数" value={s.danmaku_count.toLocaleString()} subtitle="条弹幕" icon={MessageSquare} color={COLORS.pink} />
          <StatCard title="根评论" value={s.root_comment_count.toLocaleString()} subtitle="条热门评论" icon={MessageCircle} color={COLORS.blue} />
          <StatCard title="追评总数" value={s.reply_count.toLocaleString()} subtitle={`平均 ${s.avg_reply_per_root} 条/根评`} icon={Users} color={COLORS.green} />
          <StatCard title="最高点赞" value={s.max_likes >= 10000 ? `${(s.max_likes / 10000).toFixed(1)}万` : s.max_likes} subtitle="单条评论" icon={Heart} color={COLORS.red} />
        </div>

        {/* Danmaku Time Chart */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp size={16} style={{ color: COLORS.pink }} />
              弹幕时间分布
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={dmTimeChart}>
                <defs>
                  <linearGradient id="dmGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLORS.pink} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={COLORS.pink} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  formatter={(value: number) => [`${value} 条`, '弹幕数']}
                />
                <Area type="monotone" dataKey="count" stroke={COLORS.pink} strokeWidth={2.5} fill="url(#dmGrad)" dot={{ r: 4, fill: 'white', stroke: COLORS.pink, strokeWidth: 2 }} />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Sentiment Analysis Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Danmaku Sentiment Pie */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Heart size={16} style={{ color: COLORS.pink }} />
                弹幕情感分布
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={dmSentimentPie} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {dmSentimentPie.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <p className="text-center text-sm text-muted-foreground">
                平均情感分数: <span className="font-semibold" style={{ color: COLORS.pink }}>{data.sentiment.danmaku.avg_score.toFixed(3)}</span>
              </p>
            </CardContent>
          </Card>

          {/* Comment Sentiment Pie */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Heart size={16} style={{ color: COLORS.green }} />
                评论情感分布
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={cmtSentimentPie} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {cmtSentimentPie.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <p className="text-center text-sm text-muted-foreground">
                平均情感分数: <span className="font-semibold" style={{ color: COLORS.green }}>{data.sentiment.comment.avg_score.toFixed(3)}</span>
              </p>
            </CardContent>
          </Card>

          {/* Level Distribution */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Users size={16} style={{ color: COLORS.blue }} />
                评论者等级分布
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={levelChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="level" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                  <Bar dataKey="count" fill={COLORS.blue} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        {/* Keywords Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Danmaku Keywords */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <MessageSquare size={16} style={{ color: COLORS.pink }} />
                弹幕关键词 Top10
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={dmKeywordsChart} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis dataKey="word" type="category" tick={{ fontSize: 11 }} width={60} />
                  <Tooltip contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                  <Bar dataKey="count" fill={COLORS.pink} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Comment Keywords */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <MessageCircle size={16} style={{ color: COLORS.green }} />
                评论关键词 Top10
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={cmtKeywordsChart} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis dataKey="word" type="category" tick={{ fontSize: 11 }} width={60} />
                  <Tooltip contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                  <Bar dataKey="count" fill={COLORS.green} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        {/* Heatmap + Type Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Heatmap Bar */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Clock size={16} style={{ color: COLORS.orange }} />
                弹幕密度分布 (每10秒)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={heatmapChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="time" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={50} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                  <Bar dataKey="count" fill={COLORS.orange} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Danmaku Type */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <BarChart3 size={16} style={{ color: COLORS.purple }} />
                弹幕类型分布
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={typeChart} cx="50%" cy="50%" outerRadius={80} dataKey="count" label={({ type, percent }) => `${type} ${(percent * 100).toFixed(0)}%`}>
                    {typeChart.map((_, i) => (
                      <Cell key={i} fill={TYPE_COLORS[i % TYPE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        {/* Top Comments Table */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <ThumbsUp size={16} style={{ color: COLORS.pink }} />
              高赞评论 Top10
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="text-left py-2 px-3 font-medium">排名</th>
                    <th className="text-left py-2 px-3 font-medium">评论内容</th>
                    <th className="text-center py-2 px-3 font-medium">点赞</th>
                    <th className="text-center py-2 px-3 font-medium">回复</th>
                    <th className="text-center py-2 px-3 font-medium">用户</th>
                    <th className="text-center py-2 px-3 font-medium">等级</th>
                    <th className="text-center py-2 px-3 font-medium">情感</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_comments.map((c, i) => (
                    <tr key={i} className="border-b hover:bg-gray-50 transition-colors">
                      <td className="py-2.5 px-3">
                        <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                          i === 0 ? 'bg-yellow-100 text-yellow-700' :
                          i === 1 ? 'bg-gray-100 text-gray-600' :
                          i === 2 ? 'bg-orange-100 text-orange-700' :
                          'bg-gray-50 text-gray-500'
                        }`}>
                          {i + 1}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 max-w-md truncate">{c.content}</td>
                      <td className="py-2.5 px-3 text-center font-semibold" style={{ color: COLORS.pink }}>
                        {c.likes >= 10000 ? `${(c.likes / 10000).toFixed(1)}万` : c.likes.toLocaleString()}
                      </td>
                      <td className="py-2.5 px-3 text-center text-muted-foreground">{c.replies}</td>
                      <td className="py-2.5 px-3 text-center">{c.user}</td>
                      <td className="py-2.5 px-3 text-center">
                        <span className="text-xs px-1.5 py-0.5 rounded" style={{ backgroundColor: COLORS.blue + '18', color: COLORS.blue }}>
                          Lv.{c.level}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-center"><SentimentBadge sentiment={c.sentiment} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Footer */}
        <footer className="text-center text-xs text-muted-foreground pb-4">
          <p>B站视频数据分析看板 · 数据基于弹幕与评论分析生成 · {new Date().toLocaleDateString('zh-CN')}</p>
        </footer>
      </main>
    </div>
  );
}
