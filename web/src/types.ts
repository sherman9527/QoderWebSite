import type { BlockType } from "./template/blocks";

export interface Source {
  id: string;
  url: string;
  label: string;
  publisher?: string;
  retrieved?: string;
}

export interface PageImage {
  file: string;
  alt: string;
  caption?: string;
  source_page?: string;
  /** 缺省 photo（引用图）。illustration 是本项目自画的示意图：禁带 source_page，必带 based_on。 */
  kind?: "photo" | "illustration";
  based_on?: string[];
  width?: number;
  height?: number;
}

export interface Block {
  type: BlockType;
  [key: string]: unknown;
}

export interface Section {
  id: string;
  title: string;
  anchor?: string;
  intro?: string;
  images?: PageImage[];
  blocks: Block[];
}

export interface Theme {
  token: string;
  hero_motif?: string;
  hero_note?: string;
}

export interface TopicData {
  topic: string;
  category?: string;
  tags?: string[];
  subtitle?: string;
  reader?: string;
  lede?: string;
  generated_date: string;
  theme: Theme;
  /** 声明式封面；不写则退回「最宽的一张」（见 coverOf）。 */
  cover?: PageImage;
  data_as_of?: string;
  research_mode?: "online" | "offline" | "replay";
  /** 生成阶段用 validate.reading_minutes 算好；模板只显示，不再自己数一遍。 */
  reading_minutes?: number;
  sections: Section[];
  sources: Source[];
}

/** 索引主页的一条卡片数据：从某个领域的 data.json 抽出来的摘要。 */
export interface IndexEntry {
  topic: string;
  category: string;
  subtitle?: string;
  tags: string[];
  href: string;
  cover?: PageImage;
  sections: number;
  minutes: number;
  generatedDate: string;
  /** 第一次上架那天（最早那篇日期页的日期），索引排序用它——不是 generatedDate。 */
  created: string;
  dataAsOf?: string;
  token: string;
}
