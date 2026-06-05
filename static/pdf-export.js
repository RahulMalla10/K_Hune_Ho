// Pdf -export not fully baked feature of khuneho
(function (global) {
  const MARGIN = 22;
  const PAGE_W = 210;
  const PAGE_H = 297;
  const CONTENT_W = PAGE_W - MARGIN * 2;
  const BODY_SIZE = 10;
  const META_SIZE = 9;
  const SECTION_GAP = 8;
  const ACCENT = [2, 132, 199];
  const TEXT = [15, 23, 42];
  const MUTED = [100, 116, 139];
  const LINE = [226, 232, 240];

  function slugify(text) {
    return (text || "report")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 48) || "report";
  }

  function escapeHtml(text) {
    return String(text ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatDomainName(domain) {
    return domain.charAt(0).toUpperCase() + domain.slice(1);
  }

  function parseReportSections(reportText) {
    if (!reportText) return [];
    const sections = [];
    let current = { title: "Overview", lines: [] };
    const pushCurrent = () => {
      const body = current.lines.join("\n").trim();
      if (current.title || body) sections.push({ title: current.title, body });
    };

    reportText.split("\n").forEach((line) => {
      const sectionMatch = line.match(/^===\s*(.+?)\s*===$/);
      const domainMatch = line.match(/^##\s+(.+)$/);
      if (sectionMatch) {
        pushCurrent();
        current = { title: sectionMatch[1].trim(), lines: [] };
        return;
      }
      if (domainMatch) {
        pushCurrent();
        current = { title: domainMatch[1].trim(), lines: [] };
        return;
      }
      if (line.match(/^------/)) return;
      current.lines.push(line);
    });
    pushCurrent();
    return sections.filter((s) => s.title || s.body);
  }

  function linesToBlocks(body) {
    const blocks = [];
    body.split("\n").forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      if (trimmed.startsWith("•")) {
        blocks.push({ type: "bullet", text: trimmed.replace(/^•\s*/, "") });
      } else if (/^https?:\/\//i.test(trimmed)) {
        blocks.push({ type: "meta", text: trimmed });
      } else if (/^\d+\./.test(trimmed)) {
        blocks.push({ type: "numbered", text: trimmed });
      } else {
        blocks.push({ type: "paragraph", text: trimmed });
      }
    });
    return blocks;
  }

  function buildFullDocument(result) {
    const topic = result.topic || "Analysis";
    const sections = parseReportSections(result.report_text || "").map((sec) => ({
      title: sec.title,
      blocks: linesToBlocks(sec.body),
    }));
    return {
      kind: "full",
      topic,
      label: "Full analysis report",
      filenamePrefix: "khuneho-full-report",
      sections:
        sections.length > 0
          ? sections
          : [{ title: "Report", blocks: [{ type: "paragraph", text: "No report content available." }] }],
    };
  }

  function buildCompleteDocument(result) {
    const topic = result.topic || "Analysis";
    const sections = [];

    sections.push({
      title: "Executive summary",
      blocks: [
        { type: "paragraph", text: topic },
        { type: "meta", text: `Articles analyzed: ${result.article_count ?? "—"}` },
        {
          type: "meta",
          text: `Active domains: ${Object.keys(result.routed_domains || {}).length}`,
        },
        {
          type: "meta",
          text: `Model: ${result.model_mode === "low-power" ? "CPU" : "GPU"}`,
        },
        { type: "meta", text: `Generated: ${new Date().toLocaleString()}` },
      ],
    });

    if (result.causal_chains?.length) {
      const blocks = [];
      result.causal_chains.forEach((chain) => {
        const rank = chain.display_rank || chain.rank || "?";
        const conf = Number(chain.confidence).toFixed(2);
        blocks.push({
          type: "subheading",
          text: `Rank ${rank} · Confidence ${conf}`,
        });
        blocks.push({ type: "paragraph", text: chain.chain || "" });
      });
      sections.push({ title: "Causal trace", blocks });
    }

    const agentResults = result.agent_results || {};
    const weights = result.routed_domains || {};
    const domains = Object.entries(agentResults).sort(
      (a, b) => (weights[b[0]] || 0) - (weights[a[0]] || 0)
    );

    if (domains.length) {
      const blocks = [];
      domains.forEach(([domain, data]) => {
        const w = weights[domain] ? Number(weights[domain]).toFixed(2) : "—";
        blocks.push({
          type: "subheading",
          text: `${formatDomainName(domain)} · weight ${w}`,
        });
        if (data.predictions?.length) {
          data.predictions.forEach((p, i) => {
            blocks.push({
              type: "numbered",
              text: `${i + 1}. ${p.prediction || "N/A"}`,
            });
            blocks.push({
              type: "meta",
              text: `Confidence ${p.confidence ?? "N/A"} · Timeline ${p.timeline ?? "N/A"}`,
            });
          });
        } else {
          blocks.push({
            type: "paragraph",
            text: data.error || "No predictions generated.",
          });
        }
      });
      sections.push({ title: "Domain predictions", blocks });
    }

    if (result.timeline?.length) {
      sections.push({
        title: "Timeline",
        blocks: result.timeline.map((item) => ({
          type: "bullet",
          text: `${item.date || "Unknown"} — ${item.title || ""}`,
        })),
      });
    }

    if (result.articles?.length) {
      const blocks = [];
      result.articles.forEach((article, i) => {
        blocks.push({
          type: "numbered",
          text: `${i + 1}. ${article.title || "Untitled"}`,
        });
        if (article.url) blocks.push({ type: "meta", text: article.url });
        blocks.push({
          type: "meta",
          text: `${article.date || "Unknown date"} · ${article.source || "Unknown source"}`,
        });
      });
      sections.push({ title: "News sources", blocks });
    }

    return {
      kind: "complete",
      topic,
      label: "Complete report",
      filenamePrefix: "khuneho-complete-report",
      sections,
    };
  }

  function renderPreviewHtml(doc) {
    const sectionsHtml = doc.sections
      .map((section) => {
        const blocksHtml = section.blocks
          .map((block) => {
            if (block.type === "subheading") {
              return `<p class="pdf-preview-subheading">${escapeHtml(block.text)}</p>`;
            }
            if (block.type === "bullet") {
              return `<p class="pdf-preview-bullet">${escapeHtml(block.text)}</p>`;
            }
            if (block.type === "numbered") {
              return `<p class="pdf-preview-numbered">${escapeHtml(block.text)}</p>`;
            }
            if (block.type === "meta") {
              return `<p class="pdf-preview-meta">${escapeHtml(block.text)}</p>`;
            }
            return `<p class="pdf-preview-paragraph">${escapeHtml(block.text)}</p>`;
          })
          .join("");
        return `
          <section class="pdf-preview-section">
            <h4 class="pdf-preview-section-title">${escapeHtml(section.title)}</h4>
            <div class="pdf-preview-section-body">${blocksHtml}</div>
          </section>`;
      })
      .join("");

    return `
      <article class="pdf-preview-document">
        <header class="pdf-preview-doc-header">
          <span class="pdf-preview-brand">KHUNEHO</span>
          <h3 class="pdf-preview-doc-topic">${escapeHtml(doc.topic)}</h3>
          <p class="pdf-preview-doc-label">${escapeHtml(doc.label)}</p>
        </header>
        ${sectionsHtml}
      </article>`;
  }

  function writePdf(docModel) {
    const { jsPDF } = global.jspdf;
    const pdf = new jsPDF({ unit: "mm", format: "a4" });
    let y = MARGIN;
    let pageNum = 1;

    function footer() {
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(8);
      pdf.setTextColor(...MUTED);
      pdf.text(`KHUNEHO · Page ${pageNum}`, PAGE_W / 2, PAGE_H - 12, { align: "center" });
    }

    function newPage() {
      footer();
      pdf.addPage();
      pageNum += 1;
      y = MARGIN;
    }

    function ensureSpace(needed) {
      if (y + needed > PAGE_H - MARGIN - 10) newPage();
    }

    function drawDocHeader() {
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(18);
      pdf.setTextColor(...TEXT);
      pdf.text("KHUNEHO", MARGIN, y);
      y += 8;

      pdf.setFontSize(11);
      pdf.setFont("helvetica", "normal");
      pdf.setTextColor(...MUTED);
      const topicLines = pdf.splitTextToSize(docModel.topic, CONTENT_W);
      topicLines.forEach((line) => {
        ensureSpace(6);
        pdf.text(line, MARGIN, y);
        y += 5.5;
      });

      pdf.setFontSize(9);
      pdf.text(docModel.label, MARGIN, y);
      y += 6;

      pdf.setDrawColor(...LINE);
      pdf.line(MARGIN, y, PAGE_W - MARGIN, y);
      y += SECTION_GAP;
    }

    function drawSectionTitle(title) {
      ensureSpace(14);
      y += 3;
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(11);
      pdf.setTextColor(...ACCENT);
      pdf.text(title, MARGIN, y);
      y += 7;
    }

    function drawSubheading(text) {
      ensureSpace(10);
      y += 2;
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(10);
      pdf.setTextColor(...TEXT);
      const lines = pdf.splitTextToSize(text, CONTENT_W);
      lines.forEach((line) => {
        ensureSpace(5);
        pdf.text(line, MARGIN, y);
        y += 5;
      });
    }

    function drawParagraph(text, indent = 0) {
      if (!text) return;
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(BODY_SIZE);
      pdf.setTextColor(...TEXT);
      const lines = pdf.splitTextToSize(text.trim(), CONTENT_W - indent);
      lines.forEach((line) => {
        ensureSpace(5.5);
        pdf.text(line, MARGIN + indent, y);
        y += 5.2;
      });
      y += 2;
    }

    function drawMeta(text, indent = 0) {
      if (!text) return;
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(META_SIZE);
      pdf.setTextColor(...MUTED);
      const lines = pdf.splitTextToSize(text.trim(), CONTENT_W - indent);
      lines.forEach((line) => {
        ensureSpace(5);
        pdf.text(line, MARGIN + indent, y);
        y += 4.6;
      });
      y += 1;
    }

    function drawBullet(text) {
      drawParagraph(`• ${text}`, 2);
    }

    drawDocHeader();

    docModel.sections.forEach((section, index) => {
      if (index > 0) y += 2;
      drawSectionTitle(section.title);
      section.blocks.forEach((block) => {
        if (block.type === "subheading") drawSubheading(block.text);
        else if (block.type === "bullet") drawBullet(block.text);
        else if (block.type === "numbered") drawParagraph(block.text);
        else if (block.type === "meta") drawMeta(block.text, 2);
        else drawParagraph(block.text);
      });
      y += 2;
    });

    footer();
    const stamp = new Date().toISOString().slice(0, 10);
    pdf.save(`${docModel.filenamePrefix}-${slugify(docModel.topic)}-${stamp}.pdf`);
  }

  function downloadFromDocument(docModel) {
    writePdf(docModel);
  }

  function downloadCompleteReportPdf(result) {
    downloadFromDocument(buildCompleteDocument(result));
  }

  function downloadFullReportPdf(reportText, topic) {
    downloadFromDocument(
      buildFullDocument({ topic, report_text: reportText })
    );
  }

  global.KhunehoPdf = {
    buildCompleteDocument,
    buildFullDocument,
    renderPreviewHtml,
    downloadCompleteReportPdf,
    downloadFullReportPdf,
    parseReportSections,
  };
})(window);
