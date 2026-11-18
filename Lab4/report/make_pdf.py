"""Собирает два PDF из Markdown (pandoc -> HTML с MathML -> Chromium через Playwright):
   report/Lab4_subvector.md        -> Lab4/Lab4_subvector.pdf               (отчёт по лабе)
   ai_research/AI_comparison.md    -> Lab4/ai_research/AI_comparison.pdf     (исследование ИИ)
Запуск из любого каталога: python3 Lab4/report/make_pdf.py"""
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent          # Lab4/report
LAB4 = HERE.parent
BUILD = HERE / "build"
BUILD.mkdir(exist_ok=True)
CSS = HERE / "report.css"

DOCS = [
    (HERE / "Lab4_subvector.md", LAB4, LAB4 / "Lab4_subvector.pdf",
     "Лабораторная 4. subvector: динамический массив и стратегии роста", "Lab4 · subvector"),
    (LAB4 / "ai_research" / "AI_comparison.md", LAB4 / "ai_research", LAB4 / "ai_research" / "AI_comparison.pdf",
     "Lab4 · subvector: сравнение решений ИИ", "Lab4 · исследование ИИ"),
]


def build(src, resources, pdf, title, footer):
    html = BUILD / (src.stem + ".html")
    subprocess.run(["pandoc", str(src), "-o", str(html), "--standalone", "--mathml", "--toc", "--toc-depth=2",
                    "--css", str(CSS), "--resource-path", str(resources), "--metadata", f"title={title}",
                    "--metadata", "lang=ru", "--embed-resources", "--no-highlight"], check=True)
    js = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto('file://{html}', {{ waitUntil: 'load' }});
  await p.pdf({{ path: '{pdf}', format: 'A4', printBackground: true,
    margin: {{ top: '16mm', bottom: '16mm', left: '15mm', right: '15mm' }},
    displayHeaderFooter: true, headerTemplate: '<span></span>',
    footerTemplate: '<div style="font-size:8px;width:100%;text-align:center;color:#888">' +
      '{footer} · стр. <span class="pageNumber"></span> из <span class="totalPages"></span></div>' }});
  await b.close();
}})();
"""
    subprocess.run(["node", "-e", js], check=True)
    print("pdf:", pdf)


for doc in DOCS:
    build(*doc)
