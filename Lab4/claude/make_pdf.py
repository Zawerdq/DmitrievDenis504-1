"""REPORT.md -> report.html (pandoc, формулы в MathML) -> Lab4_subvector_report.pdf (Chromium через Playwright)."""
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
html = HERE / "build" / "report.html"
pdf = HERE / "Lab4_subvector_report.pdf"
html.parent.mkdir(exist_ok=True)

subprocess.run(["pandoc", str(HERE / "REPORT.md"), "-o", str(html), "--standalone", "--mathml", "--toc",
                "--toc-depth=2", "--css", str(HERE / "report.css"), "--resource-path", str(HERE),
                "--metadata", "title=Лабораторная 4. subvector: динамический массив и стратегии роста",
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
      'Lab4 · subvector · стр. <span class="pageNumber"></span> из <span class="totalPages"></span></div>' }});
  await b.close();
}})();
"""
subprocess.run(["node", "-e", js], check=True)
print("pdf:", pdf)
