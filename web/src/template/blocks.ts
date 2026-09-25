/**
 * 区块类型枚举 —— 与 config/topic_data.schema.json 的 $defs.blockType.enum 必须完全一致。
 * 一致性由 tests/test_contract.py 断言，改一处忘改另一处会立刻红。
 */
export const BLOCK_TYPES = [
  "prose",
  "keyvalue_table",
  "timeline",
  "price_table",
  "card_grid",
  "steps",
  "quote",
  "fact_strip",
  "bar_chart",
  "compare",
  "note",
] as const;

export type BlockType = (typeof BLOCK_TYPES)[number];
