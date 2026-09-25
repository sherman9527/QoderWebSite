import { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { TopicPage } from "../template/TopicPage";
import { THEMES } from "../tokens";
import type { TopicData } from "../types";
import sample from "../../../tests/fixtures/mini_data.json";

/**
 * 工作台：把 data.json 灌进模板，切着看 10 套主题。
 *
 * 它和产物用同一个 TopicPage，所以在这里看到的排版就是最终静态页的排版——
 * 模板真身唯一，不存在"工作台好看、产物另一回事"。
 */
function Workbench() {
  const [token, setToken] = useState<string>("coffee-roast");
  const [raw, setRaw] = useState<string>(JSON.stringify(sample, null, 1));
  const [error, setError] = useState<string>("");

  const data = useMemo<TopicData | null>(() => {
    try {
      const parsed = JSON.parse(raw) as TopicData;
      parsed.theme = { ...parsed.theme, token };
      setError("");
      return parsed;
    } catch (e) {
      setError(String(e));
      return null;
    }
  }, [raw, token]);

  return (
    <>
      <div className="bar">
        <strong>黄金模板工作台</strong>
        <select value={token} onChange={(e) => setToken(e.target.value)}>
          {Object.keys(THEMES).map((k) => (
            <option key={k} value={k}>
              {THEMES[k].label}
            </option>
          ))}
        </select>
        <label>
          data.json
          <input
            type="file"
            accept="application/json"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) f.text().then(setRaw);
            }}
          />
        </label>
        {error && <span className="err">{error}</span>}
      </div>
      {data && <TopicPage data={data} />}
      <style>{`
        .bar{position:sticky;top:0;z-index:10;display:flex;gap:.8rem;align-items:center;
          flex-wrap:wrap;padding:.5rem .9rem;background:#111;color:#eee;font-size:.8rem;
          font-family:system-ui,sans-serif}
        .bar select,.bar input{font-size:.8rem}
        .bar .err{color:#f88}
      `}</style>
    </>
  );
}

createRoot(document.getElementById("root")!).render(<Workbench />);
