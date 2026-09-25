/**
 * 版心令牌：索引页与专题页必须共用，否则点卡片时整栏会横向跳动。
 * （实测两版各用 3vw/4vw，3737px 下内容左边缘 549 vs 597，差 48px。）
 */
export const LAYOUT_CSS = `:root{
  --pad:clamp(1.1rem, 4vw, 5rem);
  --cap:168rem;
  --col:min(100% - var(--pad) * 2, var(--cap));
  /* 文章版心与索引版心是两回事：索引是照片墙，越宽越好；
     文章是长文，宽度用来放"结构"（目录栏 + 正文列），不是用来拉长句子。
     一条列只有一个右边界：封面、正文、图、表、卡片全部收在同一个边上。
     以前正文 44rem、图 50rem、表格/卡片撑满"正文 + 24rem 余量"，
     三条边差到 384px，开发者实测反馈"看上去很不平整"（W-81）。
     外壳 = 目录栏 14 + 间距 2.5 + 正文列 46，正好等于「一栏 + 正文列」，
     封面标题才和正文左边缘对齐、右边缘也一起收口。 */
  --shell:min(100% - var(--pad) * 2, 62.5rem);
  --rail:14rem;
  --measure:46rem;
}`;

export const LAYOUT_MOBILE_CSS = `@media (max-width:640px){:root{--pad:.95rem}}`;
