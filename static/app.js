// static/app.js — GhostMail Frontend
document.addEventListener("DOMContentLoaded", () => {
    // ── State ──────────────────────────────────────────────────────
    let recipients = [];
    let columns = [];
    let activeJobId = null;
    let pollTimer = null;
    let quillCompose = null;
    let quillCampaign = null;
    let composeMode = { compose: 'richtext', campaign: 'richtext' };
    let suggestedSender = '';
    let suggestedSenderName = '';
    let senderLocked = false;
    let countdownTimer = null;
    let availableProviders = [];  // populated from /api/config
    let activeProviderId = "";
    let opsTimer = null;
    let historyJobs = [];
    let scheduledJobs = [];
    let currentScheduledJob = null;
    let operationsSnapshot = null;

    // ── DOM Cache ──────────────────────────────────────────────────
    const $ = (id) => document.getElementById(id);
    const el = {
        // Auth
        loginOverlay:   $("login-overlay"),
        loginForm:      $("login-form"),
        loginPwd:       $("login-password"),
        loginBtn:       $("login-btn"),
        loginError:     $("login-error"),
        logoutBtn:      $("logout-btn"),
        app:            $("app"),
        // Compose
        singleForm:     $("single-form"),
        btnSendSingle:  $("btn-send-single"),
        // Campaign — upload
        dropZone:       $("drop-zone"),
        fileInput:      $("file-input"),
        fileInfo:       $("file-info"),
        fileName:       $("file-name"),
        recipientCount: $("recipient-count"),
        btnClearFile:   $("btn-clear-file"),
        varChips:       $("var-chips"),
        varChipsList:   $("var-chips-list"),
        dataPreview:    $("data-preview"),
        previewShowing: $("preview-showing"),
        previewThead:   $("preview-thead"),
        previewTbody:   $("preview-tbody"),
        // Campaign — compose
        bFromEmail:     $("b-from-email"),
        bFromName:      $("b-from-name"),
        bSubject:       $("b-subject"),
        bContent:       $("b-content"),
        bAttachments:   $("b-attachments"),
        bPdfEnabled:    $("b-pdf-enabled"),
        bPdfOptions:    $("b-pdf-options"),
        bPdfFilename:   $("b-pdf-filename"),
        bPdfContent:    $("b-pdf-content"),
        bPdfPreview:    $("b-pdf-preview"),
        bInterval:      $("b-interval"),
        intervalDisplay:$("interval-display"),
        btnPreview:     $("btn-preview"),
        btnSendBulk:    $("btn-send-bulk"),
        // Campaign — progress
        progressSection:$("progress-section"),
        pctText:        $("pct-text"),
        countText:      $("count-text"),
        progressBar:    $("progress-bar"),
        spinIndicator:  $("spin-indicator"),
        currentEmail:   $("current-email"),
        statTotal:      $("stat-total"),
        statSuccess:    $("stat-success"),
        statFailed:     $("stat-failed"),
        timeEstimate:   $("time-estimate"),
        btnPause:       $("btn-pause"),
        btnResume:      $("btn-resume"),
        btnCancel:      $("btn-cancel"),
        failedSection:  $("failed-section"),
        btnToggleFailed:$("btn-toggle-failed"),
        failedCountLabel:$("failed-count-label"),
        failedList:     $("failed-list"),
        // History
        historyTbody:   $("history-tbody"),
        btnRefreshHistory:$("btn-refresh-history"),
        historyInsights: $("history-insights"),
        historySearch:  $("history-search"),
        historyStatusFilter: $("history-status-filter"),
        historyKindFilter: $("history-kind-filter"),
        providerLabel:  $("provider-label"),
        providerSwitcher: $("provider-switcher"),
        btnRefreshOperations: $("btn-refresh-operations"),
        opsAutorefresh: $("ops-autorefresh"),
        opsLiveDot:     $("ops-live-dot"),
        opsEventFilter: $("ops-event-filter"),
        opsEventCount:  $("ops-event-count"),
        opsSourceNote:  $("ops-source-note"),
        opsActiveProvider: $("ops-active-provider"),
        opsResolvedSender: $("ops-resolved-sender"),
        opsScheduler: $("ops-scheduler"),
        opsDatabasePath: $("ops-database-path"),
        opsUptime: $("ops-uptime"),
        opsActiveWorkers: $("ops-active-workers"),
        opsJobStatusStats: $("ops-job-status-stats"),
        opsScheduledStats: $("ops-scheduled-stats"),
        opsProviderStats: $("ops-provider-stats"),
        opsWorkersTbody: $("ops-workers-tbody"),
        opsRecentJobs: $("ops-recent-jobs"),
        opsRecentEvents: $("ops-recent-events"),
        // Scheduled
        scheduledTbody: $("scheduled-tbody"),
        btnRefreshScheduled: $("btn-refresh-scheduled"),
        sScheduleTime:  $("s-schedule-time"),
        bScheduleTime:  $("b-schedule-time"),
        btnSchedSingle: $("btn-schedule-single"),
        btnSchedBulk:   $("btn-schedule-bulk"),
        scheduledModal: $("scheduled-modal"),
        btnCloseScheduledModal: $("btn-close-scheduled-modal"),
        btnCloseScheduledModal2: $("btn-close-scheduled-modal-2"),
        btnSaveScheduled: $("btn-save-scheduled"),
        scheduledDetailId: $("scheduled-detail-id"),
        scheduledDetailType: $("scheduled-detail-type"),
        scheduledDetailStatus: $("scheduled-detail-status"),
        scheduledDetailProvider: $("scheduled-detail-provider"),
        scheduledEditTime: $("scheduled-edit-time"),
        scheduledDetailErrorWrap: $("scheduled-detail-error-wrap"),
        scheduledDetailSubject: $("scheduled-detail-subject"),
        scheduledDetailBody: $("scheduled-detail-body"),
        btnOpenLinkedJob: $("btn-open-linked-job"),
        // Preview modal
        previewModal:   $("preview-modal"),
        btnClosePreview:$("btn-close-preview"),
        btnClosePreview2:$("btn-close-preview-2"),
        prevFrom:       $("prev-from"),
        prevTo:         $("prev-to"),
        prevSubject:    $("prev-subject"),
        prevBody:       $("prev-body"),
        // Settings modal
        settingsModal:  $("settings-modal"),
        btnSettings:    $("btn-settings"),
        btnCloseSettings: $("btn-close-settings"),
        btnCloseSettings2: $("btn-close-settings-2"),
        providerKeyCards: $("provider-key-cards"),
        historyModal: $("history-modal"),
        btnCloseHistoryModal: $("btn-close-history-modal"),
        btnCloseHistoryModal2: $("btn-close-history-modal-2"),
        historyDetailId: $("history-detail-id"),
        historyDetailKind: $("history-detail-kind"),
        historyDetailProvider: $("history-detail-provider"),
        historyDetailStatus: $("history-detail-status"),
        historyDetailDate: $("history-detail-date"),
        historyDetailSender: $("history-detail-sender"),
        historyDetailCounts: $("history-detail-counts"),
        historyDetailError: $("history-detail-error"),
        historyDetailSubject: $("history-detail-subject"),
        historyDetailFailureCount: $("history-detail-failure-count"),
        historyDetailFailures: $("history-detail-failures"),
        // Toasts
        toasts:         $("toasts"),
        year:           $("year"),
        senderDisplay:  $("sender-display"),
        sFromEmail:     $("s-from-email"),
        sFromName:      $("s-from-name"),
    };

    // ── Init ───────────────────────────────────────────────────────
    if (el.year) el.year.textContent = new Date().getFullYear();
    setupListeners();
    initQuillEditors();
    bootstrapApp();

    // ════════════════════════════════════════════════════════════════
    //  EVENT LISTENERS
    // ════════════════════════════════════════════════════════════════

    function setupListeners() {
        // Auth
        el.loginForm?.addEventListener("submit", (e) => { e.preventDefault(); doLogin(); });
        el.logoutBtn?.addEventListener("click", doLogout);

        // Tabs
        document.querySelectorAll(".tab-btn").forEach(btn => {
            btn.addEventListener("click", () => switchTab(btn.dataset.tab));
        });

        // Compose
        el.btnSendSingle?.addEventListener("click", sendSingle);
        el.singleForm?.addEventListener("submit", (e) => e.preventDefault());

        // Upload
        el.dropZone?.addEventListener("click", () => el.fileInput?.click());
        el.dropZone?.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); el.fileInput?.click(); } });
        el.fileInput?.addEventListener("change", handleUpload);
        el.btnClearFile?.addEventListener("click", clearUpload);

        // Drag & drop
        ["dragenter", "dragover"].forEach(evt => el.dropZone?.addEventListener(evt, (e) => { e.preventDefault(); el.dropZone.classList.add("border-ghost-500", "bg-surface-2/50"); }));
        ["dragleave", "drop"].forEach(evt => el.dropZone?.addEventListener(evt, (e) => { e.preventDefault(); el.dropZone.classList.remove("border-ghost-500", "bg-surface-2/50"); }));
        el.dropZone?.addEventListener("drop", (e) => {
            e.preventDefault();
            if (e.dataTransfer.files.length) {
                el.fileInput.files = e.dataTransfer.files;
                el.fileInput.dispatchEvent(new Event("change"));
            }
        });

        // Interval slider
        el.bInterval?.addEventListener("input", () => {
            el.intervalDisplay.textContent = `${el.bInterval.value}s`;
        });
        el.bPdfEnabled?.addEventListener("change", () => {
            el.bPdfOptions?.classList.toggle("hidden", !el.bPdfEnabled.checked);
        });
        el.bPdfPreview?.addEventListener("click", previewPdf);

        // Preview & Send
        el.btnPreview?.addEventListener("click", showPreview);
        el.btnSendBulk?.addEventListener("click", sendBulk);
        el.btnClosePreview?.addEventListener("click", closePreview);
        el.btnClosePreview2?.addEventListener("click", closePreview);
        el.previewModal?.addEventListener("click", (e) => { if (e.target === el.previewModal) closePreview(); });

        // Pause / Resume / Cancel
        el.btnPause?.addEventListener("click", () => jobAction("pause"));
        el.btnResume?.addEventListener("click", () => jobAction("resume"));
        el.btnCancel?.addEventListener("click", () => {
            if (confirm("Cancel this campaign? Remaining emails will not be sent.")) jobAction("cancel");
        });

        // Failed toggle
        el.btnToggleFailed?.addEventListener("click", toggleFailed);

        // History
        el.btnRefreshHistory?.addEventListener("click", loadHistory);
        el.btnRefreshOperations?.addEventListener("click", loadOperations);
        el.historySearch?.addEventListener("input", renderHistory);
        el.historyStatusFilter?.addEventListener("change", renderHistory);
        el.historyKindFilter?.addEventListener("change", renderHistory);
        el.opsAutorefresh?.addEventListener("change", toggleOpsAutorefresh);
        el.opsEventFilter?.addEventListener("change", renderOperations);

        // Scheduled
        el.btnRefreshScheduled?.addEventListener("click", loadScheduled);
        el.btnSchedSingle?.addEventListener("click", scheduleSingle);
        el.btnSchedBulk?.addEventListener("click", scheduleBulk);
        el.btnCloseScheduledModal?.addEventListener("click", closeScheduledModal);
        el.btnCloseScheduledModal2?.addEventListener("click", closeScheduledModal);
        el.btnSaveScheduled?.addEventListener("click", saveScheduledChanges);
        el.btnOpenLinkedJob?.addEventListener("click", () => {
            const linkedJobId = currentScheduledJob?.linked_job || currentScheduledJob?.linked_job_summary?.id;
            if (!linkedJobId) return;
            closeScheduledModal();
            openHistoryModal(linkedJobId);
        });
        el.scheduledModal?.addEventListener("click", (e) => { if (e.target === el.scheduledModal) closeScheduledModal(); });
        el.sScheduleTime?.addEventListener("change", () => {
            el.btnSchedSingle.disabled = !el.sScheduleTime.value;
        });
        el.bScheduleTime?.addEventListener("change", () => {
            if (el.btnSchedBulk) el.btnSchedBulk.disabled = !el.bScheduleTime.value || !recipients.length;
        });

        // Settings modal
        el.btnSettings?.addEventListener("click", openSettings);
        el.btnCloseSettings?.addEventListener("click", closeSettings);
        el.btnCloseSettings2?.addEventListener("click", closeSettings);
        el.settingsModal?.addEventListener("click", (e) => { if (e.target === el.settingsModal) closeSettings(); });

        el.btnCloseHistoryModal?.addEventListener("click", closeHistoryModal);
        el.btnCloseHistoryModal2?.addEventListener("click", closeHistoryModal);
        el.historyModal?.addEventListener("click", (e) => { if (e.target === el.historyModal) closeHistoryModal(); });

        document.addEventListener("keydown", (e) => {
            if (e.key !== "Escape") return;
            closePreview();
            closeSettings();
            closeHistoryModal();
            closeScheduledModal();
        });
    }

    async function bootstrapApp() {
        if (el.app?.classList.contains("hidden")) return;
        await Promise.all([loadConfig(), loadHistory(), loadScheduled(), loadOperations()]);
    }


    // ===============================================================
    //  QUILL RICH TEXT EDITORS
    // ===============================================================

    function initQuillEditors() {
        if (typeof Quill === "undefined") { console.warn("Quill not loaded"); return; }
        const toolbarOpts = [
            [{ header: [1, 2, 3, false] }],
            ["bold", "italic", "underline", "strike"],
            [{ color: [] }, { background: [] }],
            [{ list: "ordered" }, { list: "bullet" }],
            [{ align: [] }],
            ["blockquote", "code-block"],
            ["link", "image"],
            ["clean"],
        ];

        quillCompose = new Quill("#s-editor", {
            theme: "snow",
            modules: { toolbar: toolbarOpts },
            placeholder: "Compose your email...",
        });

        quillCampaign = new Quill("#b-editor", {
            theme: "snow",
            modules: { toolbar: toolbarOpts },
            placeholder: "Dear {{First_Name}}, compose your campaign...",
        });

        // Toggle buttons
        $("s-mode-toggle")?.addEventListener("click", () => toggleEditorMode("compose"));
        $("b-mode-toggle")?.addEventListener("click", () => toggleEditorMode("campaign"));
    }

    function toggleEditorMode(which) {
        const isCompose = which === "compose";
        const quill   = isCompose ? quillCompose : quillCampaign;
        const wrap    = $(isCompose ? "s-editor-wrap" : "b-editor-wrap");
        const ta      = $(isCompose ? "s-content" : "b-content");
        const toggle  = $(isCompose ? "s-mode-toggle" : "b-mode-toggle");
        if (!quill || !wrap || !ta || !toggle) return;

        if (composeMode[which] === "richtext") {
            ta.value = quill.root.innerHTML === "<p><br></p>" ? "" : quill.root.innerHTML;
            wrap.classList.add("hidden");
            ta.classList.remove("hidden");
            toggle.innerHTML = '<i class="fas fa-wand-magic-sparkles text-xs"></i><span>Rich Text</span>';
            toggle.title = "Switch to Rich Text editor";
            toggle.classList.add("active");
            composeMode[which] = "html";
        } else {
            const html = ta.value.trim();
            if (html) quill.root.innerHTML = html;
            else quill.setContents([]);
            ta.classList.add("hidden");
            wrap.classList.remove("hidden");
            toggle.innerHTML = '<i class="fas fa-code text-xs"></i><span>HTML</span>';
            toggle.title = "Switch to HTML source";
            toggle.classList.remove("active");
            composeMode[which] = "richtext";
        }
    }

    function getEditorContent(which) {
        const isCompose = which === "compose";
        const quill = isCompose ? quillCompose : quillCampaign;
        const ta    = $(isCompose ? "s-content" : "b-content");
        if (composeMode[which] === "richtext" && quill) {
            const html = quill.root.innerHTML;
            return html === "<p><br></p>" ? "" : html.trim();
        }
        return ta?.value.trim() || "";
    }

    // ════════════════════════════════════════════════════════════════
    //  AUTH
    // ════════════════════════════════════════════════════════════════

    async function doLogin() {
        const pw = el.loginPwd?.value;
        if (!pw) return;
        setLoading(el.loginBtn, true, "Unlocking...");
        try {
            const res = await api("POST", "/api/login", { password: pw });
            if (res.success) {
                el.loginOverlay?.classList.add("hidden");
                el.app?.classList.remove("hidden");
                el.loginError?.classList.add("hidden");
                await bootstrapApp();
            } else {
                el.loginError.textContent = res.error || "Invalid password.";
                el.loginError.classList.remove("hidden");
            }
        } catch {
            el.loginError.textContent = "Connection error.";
            el.loginError.classList.remove("hidden");
        }
        setLoading(el.loginBtn, false, '<i class="fas fa-lock mr-2"></i>Unlock');
    }

    async function doLogout() {
        await api("POST", "/api/logout");
        el.app?.classList.add("hidden");
        el.loginOverlay?.classList.remove("hidden");
        el.loginPwd.value = "";
    }

    // ════════════════════════════════════════════════════════════════
    //  TABS
    // ════════════════════════════════════════════════════════════════

    function switchTab(name) {
        document.querySelectorAll(".tab-btn").forEach(b => {
            b.classList.toggle("active", b.dataset.tab === name);
            b.setAttribute("aria-selected", b.dataset.tab === name);
        });
        document.querySelectorAll(".tab-panel").forEach(p => {
            p.classList.toggle("hidden", p.id !== `panel-${name}`);
        });
        if (name === "history") loadHistory();
        if (name === "scheduled") loadScheduled();
        if (name === "operations") loadOperations();
    }

    // ════════════════════════════════════════════════════════════════
    //  SINGLE SEND
    // ════════════════════════════════════════════════════════════════

    async function sendSingle() {
        const form = el.singleForm;
        if (!form) return;
        const toEmail = form.querySelector('[name="to_email"]')?.value.trim();
        const subject = form.querySelector('[name="subject"]')?.value.trim();
        const content = getEditorContent('compose');
        if (!toEmail || !subject || !content) {
            toast("Fill in all required fields.", "error");
            return;
        }

        setLoading(el.btnSendSingle, true, "Sending...");
        try {
            const fd = new FormData(form);
            fd.set("html_content", content);
            const res = await fetch("/api/send-email", { method: "POST", body: fd });
            const data = await res.json();
            if (res.ok && data.success) {
                toast("Email sent successfully!", "success");
                loadHistory();
                loadOperations();
            } else {
                toast(data.error || `Failed (${res.status})`, "error");
            }
        } catch {
            toast("Network error.", "error");
        }
        setLoading(el.btnSendSingle, false, '<i class="fas fa-paper-plane mr-2"></i>Send Email');
    }

    // ════════════════════════════════════════════════════════════════
    //  FILE UPLOAD + DATA TABLE
    // ════════════════════════════════════════════════════════════════

    async function handleUpload() {
        const file = el.fileInput?.files[0];
        if (!file) return;

        const maxSize = 10 * 1024 * 1024;
        if (file.size > maxSize) { toast("File too large (max 10MB).", "error"); return; }

        const fd = new FormData();
        fd.append("file", file);

        el.fileInfo?.classList.remove("hidden");
        el.fileName.textContent = `Processing ${file.name}...`;
        el.recipientCount.textContent = "—";
        el.btnSendBulk.disabled = true;
        el.btnPreview.disabled = true;

        try {
            const res = await fetch("/api/upload-recipients", { method: "POST", body: fd });
            const data = await res.json();

            if (res.ok && data.success) {
                recipients = data.recipients || [];
                columns = data.columns || ["Email"];

                el.fileName.textContent = file.name;
                el.recipientCount.textContent = data.count;

                if (columns.length > 0) {
                    el.varChipsList.innerHTML = columns.map(c =>
                        `<button type="button" class="var-chip" data-var="{{${c}}}" title="Click to copy">{{${c}}}</button>`
                    ).join("");
                    el.varChips?.classList.remove("hidden");

                    el.varChipsList.querySelectorAll(".var-chip").forEach(chip => {
                        chip.addEventListener("click", () => {
                            navigator.clipboard?.writeText(chip.dataset.var);
                            toast(`Copied ${chip.dataset.var}`, "info", 1500);
                        });
                    });
                }

                renderDataTable(recipients, columns);

                if (data.invalid_skipped > 0) {
                    toast(`${data.invalid_skipped} invalid email(s) skipped.`, "warning");
                }
                if (data.count > 0) {
                    toast(`${data.count} recipients loaded.`, "success", 3000);
                    el.btnSendBulk.disabled = false;
                    el.btnPreview.disabled = false;
                } else {
                    toast("No valid recipients found.", "warning");
                }
            } else {
                toast(data.error || "Upload failed.", "error");
                clearUpload();
            }
        } catch {
            toast("Network error during upload.", "error");
            clearUpload();
        }
    }

    function renderDataTable(data, cols) {
        if (!data.length) { el.dataPreview?.classList.add("hidden"); return; }

        const maxRows = 10;
        const display = data.slice(0, maxRows);

        el.previewThead.innerHTML = `<tr>${cols.map(c => `<th class="px-3 py-2 text-left">${esc(c)}</th>`).join("")}</tr>`;

        el.previewTbody.innerHTML = display.map((row, i) =>
            `<tr class="hover:bg-surface-3/50 transition-colors">${cols.map(c =>
                `<td class="px-3 py-2 text-sm ${c === 'Email' ? 'text-ghost-300 font-mono' : 'text-gray-300'} max-w-[200px] truncate">${esc(row[c] || "")}</td>`
            ).join("")}</tr>`
        ).join("");

        el.previewShowing.textContent = data.length > maxRows
            ? `(showing ${maxRows} of ${data.length})`
            : `(${data.length} rows)`;

        el.dataPreview?.classList.remove("hidden");
    }

    function clearUpload() {
        recipients = [];
        columns = [];
        if (el.fileInput) el.fileInput.value = "";
        el.fileInfo?.classList.add("hidden");
        el.varChips?.classList.add("hidden");
        el.dataPreview?.classList.add("hidden");
        el.varChipsList.innerHTML = "";
        el.previewThead.innerHTML = "";
        el.previewTbody.innerHTML = "";
        el.btnSendBulk.disabled = true;
        el.btnPreview.disabled = true;
    }

    // ════════════════════════════════════════════════════════════════
    //  EMAIL PREVIEW
    // ════════════════════════════════════════════════════════════════

    async function showPreview() {
        if (!recipients.length) { toast("Upload recipients first.", "error"); return; }
        const subject = el.bSubject?.value.trim();
        const html = getEditorContent('campaign');
        if (!subject || !html) { toast("Fill in Subject and Content.", "error"); return; }

        try {
            const res = await api("POST", "/api/preview-email", {
                subject,
                html_content: html,
                from_email: el.bFromEmail?.value.trim() || "",
                from_name: el.bFromName?.value.trim() || "",
                recipient: recipients[0],
            });

            if (res.success && res.preview) {
                const p = res.preview;
                el.prevFrom.textContent = `${p.from_name} <${p.from_email}>`;
                el.prevTo.textContent = p.to_email;
                el.prevSubject.textContent = p.subject;
                el.prevBody.innerHTML = p.html;

                el.previewModal?.classList.remove("hidden");
                el.previewModal?.classList.add("flex");
            } else {
                toast(res.error || "Preview failed.", "error");
            }
        } catch {
            toast("Preview error.", "error");
        }
    }

    function closePreview() {
        el.previewModal?.classList.add("hidden");
        el.previewModal?.classList.remove("flex");
    }

    // ════════════════════════════════════════════════════════════════
    //  BULK SEND
    // ════════════════════════════════════════════════════════════════

    async function sendBulk() {
        if (!recipients.length) { toast("Upload recipients first.", "error"); return; }
        const subject = el.bSubject?.value.trim();
        const html = getEditorContent('campaign');
        if (!subject || !html) { toast("Fill in Subject and Content.", "error"); return; }
        const pdfConfig = getPdfAttachmentConfig();
        if (pdfConfig === false) return;

        setLoading(el.btnSendBulk, true, "Starting...");
        el.progressSection?.classList.remove("hidden");
        resetProgress(recipients.length);

        const fd = new FormData();
        fd.append("recipients", JSON.stringify(recipients));
        fd.append("subject", subject);
        fd.append("html_content", html);
        fd.append("interval", el.bInterval?.value || "4");
        fd.append("from_email_template", el.bFromEmail?.value.trim() || "");
        fd.append("from_name_template", el.bFromName?.value.trim() || "");
        if (pdfConfig) {
            fd.append("pdf_enabled", "true");
            fd.append("pdf_filename", pdfConfig.filename);
            fd.append("pdf_html_content", pdfConfig.html_content);
        }

        const files = el.bAttachments?.files;
        if (files) for (let i = 0; i < files.length; i++) fd.append("attachments", files[i]);

        try {
            const res = await fetch("/api/send-bulk", { method: "POST", body: fd });
            const data = await res.json();

            if (res.ok && data.success) {
                activeJobId = data.job_id;
                toast(`Campaign ${activeJobId} started.`, "info");
                showProgressControls("running");
                startPolling(activeJobId);
                loadOperations();

                const est = data.details?.estimated_seconds || 0;
                const finish = new Date(Date.now() + est * 1000);
                el.timeEstimate.textContent = `Est. completion: ${fmtTime(finish)} (~${fmtDuration(est)})`;
            } else {
                toast(data.error || "Failed to start campaign.", "error");
                el.progressSection?.classList.add("hidden");
            }
        } catch {
            toast("Network error.", "error");
            el.progressSection?.classList.add("hidden");
        }
        setLoading(el.btnSendBulk, false, '<i class="fas fa-rocket mr-2"></i>Start Campaign');
    }

    function getPdfAttachmentConfig() {
        if (!el.bPdfEnabled?.checked) return null;
        const filename = el.bPdfFilename?.value.trim();
        const htmlContent = el.bPdfContent?.value.trim();
        if (!filename || !htmlContent) {
            toast("Fill in the PDF filename and content.", "error");
            return false;
        }
        return { enabled: true, filename, html_content: htmlContent };
    }

    async function previewPdf() {
        if (!recipients.length) { toast("Upload recipients first.", "error"); return; }
        const pdfConfig = getPdfAttachmentConfig();
        if (!pdfConfig) { if (pdfConfig === null) toast("Enable the personalized PDF first.", "error"); return; }

        setLoading(el.bPdfPreview, true, "Rendering...");
        try {
            const res = await fetch("/api/preview-pdf", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ filename: pdfConfig.filename, html_content: pdfConfig.html_content, recipient: recipients[0] }),
            });
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                toast(data.error || "PDF preview failed.", "error");
            } else {
                const merged = res.headers.get("Content-Disposition")?.match(/filename="([^"]+)"/)?.[1] || "document.pdf";
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                window.open(url, "_blank");
                toast(`Previewing ${merged}`, "info", 3000);
                setTimeout(() => URL.revokeObjectURL(url), 60000);
            }
        } catch {
            toast("Network error.", "error");
        }
        setLoading(el.bPdfPreview, false, '<i class="fas fa-file-pdf mr-1"></i>Preview PDF');
    }

    // ════════════════════════════════════════════════════════════════
    //  PROGRESS POLLING
    // ════════════════════════════════════════════════════════════════

    function resetProgress(total) {
        el.progressBar.style.width = "0%";
        el.progressBar.className = "h-full bg-ghost-500 rounded-full transition-all duration-500";
        el.pctText.textContent = "0%";
        el.countText.textContent = `0 / ${total}`;
        el.currentEmail.textContent = "Initializing...";
        el.statTotal.textContent = total;
        el.statSuccess.textContent = "0";
        el.statFailed.textContent = "0";
        el.failedList.innerHTML = "";
        el.failedSection?.classList.add("hidden");
        el.failedList?.classList.add("hidden");
        el.spinIndicator?.classList.remove("hidden");
    }

    function startPolling(jobId) {
        stopPolling();
        pollStatus(jobId);
        pollTimer = setInterval(() => pollStatus(jobId), 2000);
    }

    function stopPolling() {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }

    async function pollStatus(jobId) {
        if (!jobId || jobId !== activeJobId) { stopPolling(); return; }
        try {
            const res = await fetch(`/api/bulk-status/${jobId}`);
            if (!res.ok) {
                if (res.status === 404) { handleComplete(null); stopPolling(); }
                return;
            }
            const data = await res.json();
            if (data.success && data.status) {
                updateProgress(data.status);
                if (!data.status.in_progress) {
                    handleComplete(data.status);
                    stopPolling();
                }
            }
        } catch (e) { console.error("Poll error:", e); }
    }

    function updateProgress(s) {
        const pct = Math.min(s.completion_percentage || 0, 100);
        el.progressBar.style.width = `${pct}%`;
        el.pctText.textContent = `${pct}%`;
        el.countText.textContent = `${s.processed || 0} / ${s.total || 0}`;
        el.currentEmail.textContent = s.current_email || "—";
        el.statSuccess.textContent = s.success_count || 0;
        el.statFailed.textContent = s.failed_count || 0;
        el.failedCountLabel.textContent = s.failed_count || 0;

        if ((s.failed_count || 0) > 0 && s.failed_emails?.length) {
            el.failedSection?.classList.remove("hidden");
            renderFailed(s.failed_emails);
        }

        showProgressControls(s.status);
        el.spinIndicator?.classList.toggle("hidden", !s.in_progress);
    }

    function renderFailed(items) {
        el.failedList.innerHTML = items.slice(0, 100).map(f =>
            `<li class="flex justify-between py-1 border-b border-surface-4/50 last:border-0">
                <span class="font-mono text-red-400 truncate mr-2">${esc(f.email)}</span>
                <span class="text-gray-500 text-right truncate">${esc(f.error?.substring(0, 80) || "")}</span>
            </li>`
        ).join("");
    }

    function handleComplete(status) {
        stopPolling();
        el.spinIndicator?.classList.add("hidden");
        showProgressControls("done");

        if (status) {
            updateProgress({ ...status, in_progress: false, completion_percentage: 100 });
            el.progressBar.style.width = "100%";

            const dur = status.completed_at && status.created_at
                ? fmtDuration(Math.round(status.completed_at - status.created_at))
                : "—";
            el.timeEstimate.textContent = `Completed in ${dur}`;
            el.currentEmail.textContent = "Finished";

            el.progressBar.classList.remove("bg-ghost-500", "bg-green-500", "bg-yellow-500", "bg-red-500");
            if (status.error || (status.failed_count > 0 && status.success_count === 0)) {
                el.progressBar.classList.add("bg-red-500");
                toast(`Campaign failed. ${status.error || ""}`, "error");
            } else if (status.failed_count > 0) {
                el.progressBar.classList.add("bg-yellow-500");
                toast(`Done: ${status.success_count} sent, ${status.failed_count} failed.`, "warning");
            } else if (status.status === "cancelled") {
                el.progressBar.classList.add("bg-yellow-500");
                toast("Campaign cancelled.", "warning");
            } else {
                el.progressBar.classList.add("bg-green-500");
                toast(`All ${status.success_count} emails sent!`, "success");
            }
        } else {
            el.timeEstimate.textContent = "Finished (status unavailable)";
            toast("Campaign finished.", "info");
        }
        activeJobId = null;
        loadHistory();
        loadScheduled();
        loadOperations();
    }

    function showProgressControls(status) {
        el.btnPause?.classList.toggle("hidden", status !== "running");
        el.btnResume?.classList.toggle("hidden", status !== "paused");
        el.btnCancel?.classList.toggle("hidden", !["running", "paused"].includes(status));
    }

    async function jobAction(action) {
        if (!activeJobId) return;
        try {
            const res = await api("POST", `/api/job/${activeJobId}/${action}`);
            if (res.success) {
                toast(`Job ${action}d.`, "info");
                if (action === "pause") showProgressControls("paused");
                else if (action === "resume") showProgressControls("running");
                else if (action === "cancel") { handleComplete(null); stopPolling(); }
            } else {
                toast(res.error || `${action} failed.`, "error");
            }
        } catch { toast("Network error.", "error"); }
    }

    function toggleFailed() {
        const hidden = el.failedList?.classList.toggle("hidden");
        const icon = el.btnToggleFailed?.querySelector("i");
        if (icon) icon.style.transform = hidden ? "" : "rotate(90deg)";
    }

    // ════════════════════════════════════════════════════════════════
    //  JOB HISTORY
    // ════════════════════════════════════════════════════════════════

    async function loadHistory() {
        try {
            const res = await api("GET", "/api/jobs?limit=0");
            if (!res.success || !res.jobs) return;
            historyJobs = res.jobs;
            renderHistoryInsights(historyJobs);
            renderHistory();
        } catch (e) { console.error("History load error:", e); }
    }

    function renderHistoryInsights(jobs) {
        if (!el.historyInsights) return;
        const sent = jobs.reduce((a, j) => a + (j.success_count || 0), 0);
        const failed = jobs.reduce((a, j) => a + (j.failed_count || 0), 0);
        const processed = sent + failed;
        const rate = processed ? Math.round((sent / processed) * 100) : null;
        const running = jobs.filter(j => ["running", "paused"].includes(j.status)).length;
        const campaigns = jobs.filter(j => j.kind !== "single").length;
        const rateColor = rate === null ? "text-gray-400" : rate >= 98 ? "text-green-400" : rate >= 90 ? "text-yellow-400" : "text-red-400";
        const cards = [
            { value: sent.toLocaleString(), label: "Emails Delivered", sub: `${processed.toLocaleString()} attempted`, icon: "paper-plane", color: "text-green-400" },
            { value: rate === null ? "—" : `${rate}%`, label: "Success Rate", sub: rate === null ? "No deliveries yet" : `${failed.toLocaleString()} failed`, icon: "bullseye", color: rateColor },
            { value: jobs.length.toLocaleString(), label: "Total Jobs", sub: `${campaigns} campaign(s)`, icon: "layer-group", color: "text-ghost-300" },
            { value: running.toLocaleString(), label: "Active Now", sub: running ? "Running or paused" : "All settled", icon: "bolt", color: running ? "text-blue-400" : "text-gray-400" },
        ];
        el.historyInsights.innerHTML = cards.map(c => `
            <div class="kpi-card">
                <div class="flex items-start justify-between">
                    <div>
                        <div class="kpi-value ${c.color}">${c.value}</div>
                        <div class="kpi-label">${c.label}</div>
                        <div class="kpi-sub">${c.sub}</div>
                    </div>
                    <i class="fas fa-${c.icon} ${c.color} opacity-60 mt-1"></i>
                </div>
            </div>`).join("");
    }

    function historyMatchesFilters(j) {
        const q = (el.historySearch?.value || "").trim().toLowerCase();
        const status = el.historyStatusFilter?.value || "all";
        const kind = el.historyKindFilter?.value || "all";
        if (status !== "all" && j.status !== status) return false;
        if (kind !== "all" && (j.kind || "campaign") !== kind) return false;
        if (q) {
            const hay = `${j.id} ${j.subject_template || ""} ${j.provider || ""} ${j.from_email || ""} ${j.from_name || ""}`.toLowerCase();
            if (!hay.includes(q)) return false;
        }
        return true;
    }

    function renderHistory() {
        if (!el.historyTbody) return;
        const jobs = (historyJobs || []).filter(historyMatchesFilters);

        if (!jobs.length) {
            const filtered = (historyJobs || []).length > 0;
            el.historyTbody.innerHTML = `<tr><td colspan="11" class="px-4 py-8 text-center text-gray-500"><i class="fas fa-${filtered ? "filter-circle-xmark" : "inbox"} text-2xl mb-2 block"></i>${filtered ? "No jobs match the current filters." : "No delivery history yet."}</td></tr>`;
            return;
        }

        el.historyTbody.innerHTML = jobs.map(j => {
            const date = j.created_at ? new Date(j.created_at * 1000).toLocaleString() : "—";
            const badge = statusBadge(j.status);
            const subj = esc((j.subject_template || "").substring(0, 40));
            const kind = j.kind === "single"
                ? '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-600/20 text-blue-300 border border-blue-600/30 ml-2">Single</span>'
                : '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-ghost-600/20 text-ghost-300 border border-ghost-600/30 ml-2">Campaign</span>';
            const processed = (j.success_count || 0) + (j.failed_count || 0);
            const rate = processed ? (j.success_count || 0) / processed : null;
            const ratePct = rate === null ? 0 : Math.round(rate * 100);
            const rateColor = rate === null ? "#4b5563" : ratePct >= 98 ? "#34d399" : ratePct >= 90 ? "#fbbf24" : "#f87171";
            const durSecs = j.completed_at && j.created_at ? j.completed_at - j.created_at : null;
            const duration = durSecs !== null ? fmtDuration(durSecs) : (["running", "paused"].includes(j.status) ? "…" : "—");
            const throughput = durSecs && processed ? `${(processed / (durSecs / 60)).toFixed(1)}/min` : "";
            return `<tr class="hover:bg-surface-3/30 transition-colors">
                <td class="px-4 py-3 font-mono text-xs text-ghost-300">${esc(j.id)}</td>
                <td class="px-4 py-3 text-xs">${esc(j.provider)} ${kind}</td>
                <td class="px-4 py-3 text-sm truncate max-w-[160px]" title="${esc(j.subject_template || "")}">${subj}</td>
                <td class="px-4 py-3 text-center">${j.total}</td>
                <td class="px-4 py-3 text-center text-green-400">${j.success_count}</td>
                <td class="px-4 py-3 text-center text-red-400">${j.failed_count}</td>
                <td class="px-4 py-3">
                    <div class="flex items-center gap-2" title="${rate === null ? "No sends recorded" : `${ratePct}% success${throughput ? ` · ${throughput}` : ""}`}">
                        <div class="rate-bar"><span style="width:${ratePct}%;background:${rateColor}"></span></div>
                        <span class="text-xs text-gray-400">${rate === null ? "—" : `${ratePct}%`}</span>
                    </div>
                </td>
                <td class="px-4 py-3 text-center">${badge}</td>
                <td class="px-4 py-3 text-xs text-gray-400" title="${throughput}">${duration}</td>
                <td class="px-4 py-3 text-xs text-gray-400">${date}</td>
                <td class="px-4 py-3 text-center">
                    <button onclick="openHistoryModal('${j.id}')" class="text-ghost-400 hover:text-ghost-300 transition-colors mr-3" title="View details">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button onclick="deleteJob('${j.id}')" class="text-gray-500 hover:text-red-400 transition-colors" title="Delete">
                        <i class="fas fa-trash-can"></i>
                    </button>
                </td>
            </tr>`;
        }).join("");
    }

    async function loadOperations() {
        try {
            const res = await api("GET", "/api/operations");
            if (!res.success || !res.operations) return;
            operationsSnapshot = res.operations;
            renderOperations();
        } catch (e) {
            console.error("Operations load error:", e);
        }
    }

    function toggleOpsAutorefresh() {
        const on = !!el.opsAutorefresh?.checked;
        el.opsLiveDot?.classList.toggle("hidden", !on);
        if (opsTimer) { clearInterval(opsTimer); opsTimer = null; }
        if (on) {
            loadOperations();
            opsTimer = setInterval(() => {
                if (!$("panel-operations")?.classList.contains("hidden")) loadOperations();
            }, 5000);
        }
    }

    function renderOperations() {
        if (!operationsSnapshot) return;

        const ops = operationsSnapshot;
        const runtime = ops.runtime || {};
        const truth = ops.single_source_of_truth || {};
        const now = ops.generated_at || Date.now() / 1000;
        const lastTickAge = runtime.scheduler_last_tick ? Math.max(0, Math.round(now - runtime.scheduler_last_tick)) : null;

        if (el.opsSourceNote) el.opsSourceNote.textContent = truth.note || "Unified runtime and database state.";
        if (el.opsActiveProvider) el.opsActiveProvider.textContent = runtime.active_provider || "—";
        if (el.opsResolvedSender) {
            el.opsResolvedSender.textContent = runtime.resolved_sender_email
                ? `${runtime.resolved_sender_name || ""} <${runtime.resolved_sender_email}>`
                : "—";
        }
        if (el.opsScheduler) {
            el.opsScheduler.textContent = runtime.scheduler_alive
                ? `Alive${lastTickAge === null ? "" : ` · last tick ${lastTickAge}s ago`}`
                : "Stopped";
        }
        if (el.opsDatabasePath) el.opsDatabasePath.textContent = truth.database_path || "—";
        if (el.opsUptime) el.opsUptime.textContent = `Uptime ${fmtDuration(runtime.uptime_seconds || 0)}`;
        if (el.opsActiveWorkers) el.opsActiveWorkers.textContent = `${runtime.active_worker_count || 0} active worker(s)`;

        renderKeyValuePills(el.opsJobStatusStats, ops.job_counts?.by_status || {}, {
            completed: "green",
            completed_with_errors: "yellow",
            failed: "red",
            running: "blue",
            paused: "yellow",
            cancelled: "gray",
        });
        renderKeyValuePills(el.opsScheduledStats, ops.scheduled_counts?.by_status || {}, {
            pending: "blue",
            running: "blue",
            sent: "green",
            failed: "red",
            cancelled: "gray",
        });

        if (el.opsProviderStats) {
            const providers = ops.providers || [];
            el.opsProviderStats.innerHTML = providers.length
                ? providers.map((provider) => `
                    <div class="inline-flex flex-col rounded-lg border border-surface-4 bg-surface-3 px-3 py-2 min-w-[120px]">
                        <span class="text-xs text-gray-500 uppercase tracking-wider">${esc(provider.label || provider.id)}</span>
                        <span class="text-sm font-semibold text-white mt-1">${provider.history_count || 0} job(s)</span>
                        <span class="text-xs text-gray-400 mt-1">Key: ${esc(provider.key_source || "none")}</span>
                    </div>
                `).join("")
                : '<div class="text-sm text-gray-500">No providers available.</div>';
        }

        if (el.opsWorkersTbody) {
            const workers = ops.active_workers || [];
            el.opsWorkersTbody.innerHTML = workers.length
                ? workers.map((worker) => {
                    const job = worker.job || {};
                    return `
                        <tr class="hover:bg-surface-3/30 transition-colors">
                            <td class="px-4 py-3 font-mono text-xs text-ghost-300">${esc(worker.job_id || "—")}</td>
                            <td class="px-4 py-3 text-xs text-gray-300">${esc(worker.thread_name || "—")}</td>
                            <td class="px-4 py-3 text-center">${worker.alive ? '<span class="text-green-400">Yes</span>' : '<span class="text-gray-500">No</span>'}</td>
                            <td class="px-4 py-3 text-sm">${job.status ? statusBadge(job.status) : '<span class="text-gray-500">No job record</span>'}</td>
                        </tr>
                    `;
                }).join("")
                : '<tr><td colspan="4" class="px-4 py-8 text-center text-gray-500">No active workers.</td></tr>';
        }

        if (el.opsRecentJobs) {
            const jobs = ops.recent_jobs || [];
            el.opsRecentJobs.innerHTML = jobs.length
                ? jobs.map((job) => `
                    <div class="bg-surface-2 border border-surface-4 rounded-lg p-4">
                        <div class="flex items-start justify-between gap-3 mb-2">
                            <div>
                                <div class="text-sm font-semibold text-white">${esc(job.subject_template || "Untitled job")}</div>
                                <div class="text-xs text-gray-500 mt-1">${esc(job.id || "—")} · ${esc(job.provider || "—")}</div>
                            </div>
                            <div>${statusBadge(job.status || "unknown")}</div>
                        </div>
                        <div class="text-xs text-gray-400">${job.success_count || 0} sent · ${job.failed_count || 0} failed · ${job.total || 0} total</div>
                    </div>
                `).join("")
                : '<div class="text-sm text-gray-500">No delivery jobs recorded.</div>';
        }

        if (el.opsRecentEvents) {
            const filter = el.opsEventFilter?.value || "all";
            const allEvents = ops.recent_events || [];
            const events = allEvents.filter((event) => {
                const lvl = (event.level || "INFO").toUpperCase();
                if (filter === "all") return true;
                if (filter === "error") return lvl === "ERROR" || lvl === "CRITICAL";
                return lvl === filter;
            });
            if (el.opsEventCount) el.opsEventCount.textContent = `${events.length} of ${allEvents.length} events`;
            el.opsRecentEvents.innerHTML = events.length
                ? events.slice().reverse().map((event) => {
                    const ts = event.timestamp ? new Date(event.timestamp * 1000).toLocaleTimeString([], { hour12: false }) : "—";
                    const lvl = (event.level || "INFO").toUpperCase();
                    const cls = (lvl === "ERROR" || lvl === "CRITICAL") ? "log-error" : lvl === "WARNING" ? "log-warn" : lvl === "DEBUG" ? "log-debug" : "log-info";
                    return `<div class="log-line">
                        <span class="log-ts">${esc(ts)}</span>
                        <span class="log-level ${cls}">${esc(lvl)}</span>
                        <span class="log-thread" title="${esc(event.thread || "")}">${esc(event.thread || "—")}</span>
                        <span class="log-msg">${esc(event.message || "")}</span>
                    </div>`;
                }).join("")
                : '<div class="px-4 py-8 text-center text-gray-500 font-sans">No backend events captured yet.</div>';
        }
    }

    window.openHistoryModal = async function(jobId) {
        try {
            const res = await api("GET", `/api/jobs/${jobId}`);
            if (!res.success || !res.job) {
                toast(res.error || "Unable to load job details.", "error");
                return;
            }

            const job = res.job;
            el.historyDetailId.textContent = job.id || "—";
            el.historyDetailKind.textContent = job.kind === "single" ? "Single email" : "Campaign";
            el.historyDetailProvider.textContent = job.provider || "—";
            el.historyDetailStatus.innerHTML = statusBadge(job.status);
            el.historyDetailDate.textContent = job.created_at ? new Date(job.created_at * 1000).toLocaleString() : "—";
            const senderText = job.from_name && job.from_email
                ? `${job.from_name} <${job.from_email}>`
                : (job.from_email || job.from_name || "—");
            el.historyDetailSender.textContent = senderText;
            const durationSecs = job.completed_at && job.created_at ? job.completed_at - job.created_at : null;
            const processedCount = (job.success_count || 0) + (job.failed_count || 0);
            const throughput = durationSecs > 0 && processedCount ? ` · ${(processedCount / (durationSecs / 60)).toFixed(1)} emails/min` : "";
            el.historyDetailCounts.textContent = `${job.success_count || 0} sent, ${job.failed_count || 0} failed, ${job.total || 0} total${durationSecs ? ` · ${fmtDuration(durationSecs)}${throughput}` : ""}`;
            el.historyDetailError.textContent = job.error || "None";
            el.historyDetailSubject.textContent = job.subject_template || "—";

            const failures = job.failures || [];
            el.historyDetailFailureCount.textContent = `${failures.length} item${failures.length === 1 ? "" : "s"}`;
            el.historyDetailFailures.innerHTML = failures.length
                ? failures.map((failure) => `
                    <li class="flex items-start justify-between gap-3 border-b border-surface-4/60 pb-2 last:border-b-0 last:pb-0">
                        <span class="font-mono text-red-300 break-all">${esc(failure.email)}</span>
                        <span class="text-gray-400 text-right">${esc(failure.error)}</span>
                    </li>
                `).join("")
                : '<li class="text-gray-500">No delivery failures recorded.</li>';

            el.historyModal?.classList.remove("hidden");
            el.historyModal?.classList.add("flex");
        } catch (e) {
            console.error("History detail error:", e);
            toast("Unable to load delivery details.", "error");
        }
    };

    function closeHistoryModal() {
        el.historyModal?.classList.add("hidden");
        el.historyModal?.classList.remove("flex");
    }

    window.deleteJob = async function(jobId) {
        if (!confirm("Delete this job record?")) return;
        try {
            await api("DELETE", `/api/jobs/${jobId}`);
            toast("Job deleted.", "info");
            loadHistory();
            loadOperations();
        } catch { toast("Delete failed.", "error"); }
    };

    function renderKeyValuePills(container, values, colorMap = {}) {
        if (!container) return;
        const entries = Object.entries(values || {}).filter(([, value]) => value !== undefined && value !== null);
        if (!entries.length) {
            container.innerHTML = '<span class="text-sm text-gray-500">No data.</span>';
            return;
        }
        container.innerHTML = entries.map(([key, value]) => {
            const color = colorMap[key] || "gray";
            return `<span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-${color}-600/20 text-${color}-300 border border-${color}-600/30">${esc(key)}: ${esc(String(value))}</span>`;
        }).join("");
    }

    function statusBadge(status) {
        const map = {
            running:              { color: "blue",   icon: "spinner fa-spin", label: "Running" },
            paused:               { color: "yellow", icon: "pause",           label: "Paused" },
            completed:            { color: "green",  icon: "check",           label: "Completed" },
            completed_with_errors:{ color: "yellow", icon: "exclamation-triangle", label: "Partial" },
            failed:               { color: "red",    icon: "xmark",           label: "Failed" },
            cancelled:            { color: "gray",   icon: "ban",             label: "Cancelled" },
        };
        const s = map[status] || { color: "gray", icon: "question", label: status };
        return `<span class="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full bg-${s.color}-600/20 text-${s.color}-300 border border-${s.color}-600/30">
            <i class="fas fa-${s.icon} mr-1 text-[10px]"></i>${s.label}
        </span>`;
    }

    // ════════════════════════════════════════════════════════════════
    //  PROVIDER SWITCHING & CONFIG
    // ════════════════════════════════════════════════════════════════

    async function loadConfig() {
        try {
            const res = await api("GET", "/api/config");
            if (!res.success) return;

            availableProviders = res.available_providers || [];
            activeProviderId = res.provider_id || "";
            senderLocked = !!res.sender_locked;

            if (el.providerLabel) el.providerLabel.textContent = res.provider;
            renderProviderSwitcher();
            suggestedSender = res.sender_email || "";
            suggestedSenderName = res.sender_name || "";

            if (el.senderDisplay) el.senderDisplay.textContent = suggestedSender;
            applySenderPolicy();
            if (!el.settingsModal?.classList.contains("hidden")) {
                renderProviderKeyCards();
            }
        } catch (e) { console.error("Config load error:", e); }
    }

    function applySenderPolicy() {
        const lockedPlaceholder = suggestedSender || "the configured sender";
        const emailFields = [el.sFromEmail, el.bFromEmail].filter(Boolean);
        const nameFields = [el.sFromName, el.bFromName].filter(Boolean);

        emailFields.forEach((field) => {
            field.disabled = senderLocked;
            if (senderLocked) {
                field.value = "";
                field.placeholder = `Using ${lockedPlaceholder}`;
                field.title = "ZeptoMail uses the configured default sender.";
            } else {
                field.placeholder = suggestedSender ? `Default: ${suggestedSender}` : "sender@yourdomain.com";
                field.title = "";
            }
        });

        nameFields.forEach((field) => {
            field.disabled = senderLocked;
            if (senderLocked) {
                field.value = "";
                field.placeholder = suggestedSenderName ? `Using ${suggestedSenderName}` : "Using configured sender name";
                field.title = "ZeptoMail uses the configured default sender name.";
            } else {
                field.placeholder = suggestedSenderName || "Sender name";
                field.title = "";
            }
        });
    }

    function renderProviderSwitcher() {
        if (!el.providerSwitcher) return;
        el.providerSwitcher.classList.remove("switching");
        el.providerSwitcher.innerHTML = availableProviders.map(p => {
            const active = p.id === activeProviderId;
            const title = p.has_key
                ? (active ? `${p.label} is active` : `Switch to ${p.label}`)
                : `${p.label}: add an API key to enable`;
            return `<button type="button" class="provider-opt${active ? " active" : ""}" data-provider="${p.id}" title="${title}" aria-pressed="${active}">
                        <span class="key-dot ${p.has_key ? "ok" : "missing"}"></span>${esc(p.label)}
                    </button>`;
        }).join("");
        el.providerSwitcher.querySelectorAll(".provider-opt").forEach(btn => {
            btn.addEventListener("click", () => {
                const id = btn.dataset.provider;
                if (id === activeProviderId) return;
                const meta = availableProviders.find(p => p.id === id);
                if (!meta?.has_key) { openSettings(); return; }
                el.providerSwitcher.classList.add("switching");
                switchProvider(id);
            });
        });
    }

    async function switchProvider(name) {
        toast(`Switching to ${name}...`, "info");
        try {
            const res = await api("POST", "/api/switch-provider", { provider: name });
            if (res.success) {
                toast(res.message || `Switched to ${res.provider}.`, "success");
                if (el.providerLabel) el.providerLabel.textContent = res.provider;
                if (res.sender_email) suggestedSender = res.sender_email;
                if (el.senderDisplay) el.senderDisplay.textContent = suggestedSender;
                if (el.sFromEmail) el.sFromEmail.placeholder = suggestedSender ? `Default: ${suggestedSender}` : "sender@yourdomain.com";
                loadConfig();
                loadOperations();
            } else {
                toast(res.error || "Switch failed.", "error");
            }
        } catch {
            toast("Network error.", "error");
        }
        el.providerSwitcher?.classList.remove("switching");
    }

    // ════════════════════════════════════════════════════════════════
    //  API KEY SETTINGS MODAL
    // ════════════════════════════════════════════════════════════════

    function openSettings() {
        el.settingsModal?.classList.remove("hidden");
        el.settingsModal?.classList.add("flex");
        renderProviderKeyCards();
    }

    function closeSettings() {
        el.settingsModal?.classList.add("hidden");
        el.settingsModal?.classList.remove("flex");
    }

    function renderProviderKeyCards() {
        if (!el.providerKeyCards) return;

        el.providerKeyCards.innerHTML = availableProviders.map(p => {
            const hasKey = p.has_key;
            const isActive = p.id === activeProviderId;
            const sourceLabel = p.key_source === 'database' ? 'Custom key'
                              : p.key_source === 'env' ? '.env file'
                              : 'Not configured';
            const sourceBadge = p.key_source === 'database'
                ? 'bg-ghost-600/20 text-ghost-300 border-ghost-600/30'
                : p.key_source === 'env'
                ? 'bg-green-600/20 text-green-300 border-green-600/30'
                : 'bg-red-600/20 text-red-300 border-red-600/30';

            return `<div class="bg-surface-3 rounded-lg border border-surface-4 p-4" id="key-card-${p.id}">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-2">
                        <i class="fas fa-${p.icon} text-${p.color}-400"></i>
                        <span class="font-medium text-white">${p.label}</span>
                        ${isActive ? '<span class="inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full border bg-ghost-600/20 text-ghost-200 border-ghost-500/30">Active</span>' : ''}
                        <span class="inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full border ${sourceBadge}">
                            ${sourceLabel}
                        </span>
                    </div>
                    ${hasKey ? `<span class="text-xs text-gray-400 font-mono">${p.key_preview}</span>` : ''}
                </div>

                <div class="flex items-center gap-2 flex-wrap">
                    <input type="password" id="key-input-${p.id}" placeholder="Paste ${p.label} API key..."
                           class="flex-1 min-w-[240px] px-3 py-2 bg-surface-2 border border-surface-5 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-ghost-500 focus:border-transparent font-mono"
                           autocomplete="off">
                    <button onclick="window._saveKey('${p.id}')" class="px-3 py-2 bg-ghost-600 hover:bg-ghost-700 text-white text-sm font-medium rounded-lg transition-colors whitespace-nowrap" title="Save and activate this provider">
                        <i class="fas fa-save mr-1"></i>Save &amp; Use
                    </button>
                    ${hasKey && !isActive ? `<button onclick="window._activateProvider('${p.id}')" class="px-3 py-2 bg-surface-4 hover:bg-surface-5 text-gray-200 text-sm rounded-lg transition-colors whitespace-nowrap" title="Use the currently saved key for this provider"><i class="fas fa-plug mr-1"></i>Use Current</button>` : ''}
                    ${p.key_source === 'database' ? `
                    <button onclick="window._removeKey('${p.id}')" class="px-3 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-300 text-sm rounded-lg transition-colors" title="Remove saved key">
                        <i class="fas fa-trash-can"></i>
                    </button>` : ''}
                </div>

                <div id="key-status-${p.id}" class="mt-2 text-xs hidden"></div>
            </div>`;
        }).join("");
    }

    // Global handlers for the settings card buttons
    window._saveKey = async function(providerId) {
        const input = $(`key-input-${providerId}`);
        const statusEl = $(`key-status-${providerId}`);
        const apiKey = input?.value.trim();

        if (!apiKey) {
            showKeyStatus(providerId, "Please enter an API key.", "error");
            return;
        }

        showKeyStatus(providerId, "Saving and testing...", "info");

        try {
            const res = await api("POST", `/api/provider-keys/${providerId}`, {
                api_key: apiKey,
                auto_switch: true,
            });

            if (res.success) {
                input.value = "";
                if (res.switched) {
                    toast(`${res.provider} activated! Key saved.`, "success");
                    if (el.providerLabel) el.providerLabel.textContent = res.provider;
                    if (res.sender_email) suggestedSender = res.sender_email;
                    if (el.senderDisplay) el.senderDisplay.textContent = suggestedSender;
                }
                showKeyStatus(providerId, res.message, "success");
                // Refresh everything
                loadConfig().then(() => renderProviderKeyCards());
                loadOperations();
            } else {
                showKeyStatus(providerId, res.error || "Failed to save key.", "error");
            }
        } catch {
            showKeyStatus(providerId, "Network error.", "error");
        }
    };

    window._activateProvider = async function(providerId) {
        try {
            const res = await api("POST", "/api/switch-provider", { provider: providerId });
            if (res.success) {
                toast(res.message || "Provider switched.", "success");
                loadConfig().then(() => renderProviderKeyCards());
                loadOperations();
            } else {
                toast(res.error || "Switch failed.", "error");
            }
        } catch {
            toast("Network error.", "error");
        }
    };

    window._removeKey = async function(providerId) {
        if (!confirm("Remove this API key? The provider may fall back to .env configuration.")) return;

        try {
            const res = await api("DELETE", `/api/provider-keys/${providerId}`);
            if (res.success) {
                toast(res.message || "Key removed.", "info");
                loadConfig().then(() => renderProviderKeyCards());
                loadOperations();
            } else {
                toast(res.error || "Remove failed.", "error");
            }
        } catch {
            toast("Network error.", "error");
        }
    };

    function showKeyStatus(providerId, message, type) {
        const statusEl = $(`key-status-${providerId}`);
        if (!statusEl) return;

        const colors = {
            success: "text-green-400",
            error: "text-red-400",
            info: "text-blue-400",
        };

        statusEl.className = `mt-2 text-xs ${colors[type] || colors.info}`;
        statusEl.textContent = message;
        statusEl.classList.remove("hidden");

        if (type !== "info") {
            setTimeout(() => statusEl.classList.add("hidden"), 8000);
        }
    }

    // ════════════════════════════════════════════════════════════════
    //  SCHEDULING
    // ════════════════════════════════════════════════════════════════

    async function scheduleSingle() {
        const form = el.singleForm;
        if (!form) return;
        const toEmail = form.querySelector('[name="to_email"]')?.value.trim();
        const subject = form.querySelector('[name="subject"]')?.value.trim();
        const content = getEditorContent('compose');
        const sendAt = el.sScheduleTime?.value;

        if (!toEmail || !subject || !content) {
            toast("Fill in all required fields.", "error");
            return;
        }
        if (!sendAt) {
            toast("Pick a date/time first.", "error");
            return;
        }

        setLoading(el.btnSchedSingle, true, "Scheduling...");
        try {
            const res = await api("POST", "/api/schedule", {
                type: "single",
                send_at: new Date(sendAt).toISOString(),
                payload: {
                    to_email: toEmail,
                    to_name: form.querySelector('[name="to_name"]')?.value.trim() || "",
                    subject: subject,
                    html_content: content,
                    from_email: form.querySelector('[name="from_email"]')?.value.trim() || "",
                    from_name: form.querySelector('[name="from_name"]')?.value.trim() || "",
                },
            });
            if (res.success) {
                toast(`Scheduled for ${new Date(sendAt).toLocaleString()}`, "success");
                el.sScheduleTime.value = "";
                el.btnSchedSingle.disabled = true;
                loadScheduled();
                loadOperations();
            } else {
                toast(res.error || "Schedule failed.", "error");
            }
        } catch {
            toast("Network error.", "error");
        }
        setLoading(el.btnSchedSingle, false, '<i class="fas fa-clock mr-1"></i>Schedule');
    }

    async function scheduleBulk() {
        if (!recipients.length) { toast("Upload recipients first.", "error"); return; }
        const subject = el.bSubject?.value.trim();
        const content = getEditorContent('campaign');
        const sendAt = el.bScheduleTime?.value;

        if (!subject || !content) { toast("Fill in Subject and Content.", "error"); return; }
        if (!sendAt) { toast("Pick a date/time first.", "error"); return; }
        const pdfConfig = getPdfAttachmentConfig();
        if (pdfConfig === false) return;

        setLoading(el.btnSchedBulk, true, "Scheduling...");
        try {
            const res = await api("POST", "/api/schedule", {
                type: "campaign",
                send_at: new Date(sendAt).toISOString(),
                payload: {
                    recipients: recipients,
                    subject: subject,
                    html_content: content,
                    interval: parseInt(el.bInterval?.value || "4"),
                    from_email_template: el.bFromEmail?.value.trim() || "",
                    from_name_template: el.bFromName?.value.trim() || "",
                    pdf_attachment: pdfConfig,
                },
            });
            if (res.success) {
                toast(`Campaign scheduled for ${new Date(sendAt).toLocaleString()}`, "success");
                el.bScheduleTime.value = "";
                el.btnSchedBulk.disabled = true;
                loadScheduled();
                loadOperations();
            } else {
                toast(res.error || "Schedule failed.", "error");
            }
        } catch {
            toast("Network error.", "error");
        }
        setLoading(el.btnSchedBulk, false, '<i class="fas fa-clock mr-1"></i>Schedule Campaign');
    }

    async function loadScheduled() {
        try {
            const res = await api("GET", "/api/scheduled-jobs?limit=0");
            if (!res.success || !res.jobs) return;
            scheduledJobs = res.jobs;

            if (res.jobs.length === 0) {
                el.scheduledTbody.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-gray-500"><i class="fas fa-calendar-xmark text-2xl mb-2 block"></i>No scheduled jobs.</td></tr>';
                stopCountdown();
                return;
            }

            el.scheduledTbody.innerHTML = res.jobs.map(j => {
                const sendAt = j.send_at ? new Date(j.send_at * 1000).toLocaleString() : "—";
                const created = j.created_at ? new Date(j.created_at * 1000).toLocaleString() : "—";
                const payload = j.payload || {};
                const subj = esc((payload.subject || "").substring(0, 40));
                const effectiveStatus = j.display_status || j.status;
                const typeLabel = j.type === "campaign"
                    ? `<span class="text-ghost-300">Campaign</span> <span class="text-gray-500 text-xs">(${(payload.recipients || []).length})</span>`
                    : `<span class="text-ghost-300">Single</span>`;
                const badge = schedBadge(effectiveStatus);
                const isPending = j.status === "pending";
                const actions = `
                    <button onclick="openScheduledModal('${j.id}')" class="text-ghost-400 hover:text-ghost-300 mr-3" title="View details">
                        <i class="fas fa-eye"></i>
                    </button>
                    ${isPending ? `<button onclick="cancelScheduled('${j.id}')" class="text-yellow-400 hover:text-yellow-300 mr-3" title="Cancel"><i class="fas fa-ban"></i></button>` : ""}
                    <button onclick="deleteScheduled('${j.id}')" class="text-gray-500 hover:text-red-400" title="Delete"><i class="fas fa-trash-can"></i></button>
                `;

                return `<tr class="hover:bg-surface-3/30 transition-colors">
                    <td class="px-4 py-3 font-mono text-xs text-ghost-300">${esc(j.id)}</td>
                    <td class="px-4 py-3 text-center text-xs">${typeLabel}</td>
                    <td class="px-4 py-3 text-sm truncate max-w-[160px]" title="${esc(payload.subject || "")}">${subj}</td>
                    <td class="px-4 py-3 text-xs text-gray-300">${sendAt}</td>
                    <td class="px-4 py-3 text-center">${badge}</td>
                    <td class="px-4 py-3 text-xs"><span class="sched-countdown" data-ts="${j.send_at || 0}" data-status="${j.status}"></span></td>
                    <td class="px-4 py-3 text-xs text-gray-400">${created}</td>
                    <td class="px-4 py-3 text-center text-sm">${actions}</td>
                </tr>`;
            }).join("");

            startCountdown();
        } catch (e) { console.error("Scheduled load error:", e); }
    }

    window.openScheduledModal = async function(scheduledId) {
        try {
            const res = await api("GET", `/api/scheduled-jobs/${scheduledId}`);
            if (!res.success || !res.job) {
                toast(res.error || "Unable to load scheduled job.", "error");
                return;
            }

            currentScheduledJob = res.job;
            const payload = currentScheduledJob.payload || {};
            const linkedJob = currentScheduledJob.linked_job_summary;
            const effectiveStatus = currentScheduledJob.display_status || currentScheduledJob.status;
            const providerId = payload._provider_id || linkedJob?.provider || "—";
            const providerMeta = availableProviders.find((entry) => entry.id === providerId);
            const canEdit = currentScheduledJob.status === "pending";

            el.scheduledDetailId.textContent = currentScheduledJob.id || "—";
            el.scheduledDetailType.textContent = currentScheduledJob.type === "campaign" ? "Campaign" : "Single email";
            el.scheduledDetailStatus.innerHTML = schedBadge(effectiveStatus);
            el.scheduledDetailProvider.textContent = providerMeta?.label || providerId;
            el.scheduledDetailSubject.textContent = payload.subject || "—";
            el.scheduledEditTime.value = formatDatetimeLocalValue(currentScheduledJob.send_at);
            el.scheduledEditTime.disabled = !canEdit;
            el.btnSaveScheduled?.classList.toggle("hidden", !canEdit);
            el.btnOpenLinkedJob?.classList.toggle("hidden", !linkedJob?.id && !currentScheduledJob.linked_job);

            if (currentScheduledJob.error) {
                el.scheduledDetailErrorWrap.textContent = currentScheduledJob.error;
                el.scheduledDetailErrorWrap.classList.remove("hidden");
            } else {
                el.scheduledDetailErrorWrap.textContent = "";
                el.scheduledDetailErrorWrap.classList.add("hidden");
            }

            el.scheduledDetailBody.innerHTML = renderScheduledPayloadPreview(currentScheduledJob);
            el.scheduledModal?.classList.remove("hidden");
            el.scheduledModal?.classList.add("flex");
        } catch (e) {
            console.error("Scheduled detail error:", e);
            toast("Unable to load scheduled job.", "error");
        }
    };

    function closeScheduledModal() {
        currentScheduledJob = null;
        el.scheduledModal?.classList.add("hidden");
        el.scheduledModal?.classList.remove("flex");
    }

    async function saveScheduledChanges() {
        if (!currentScheduledJob) return;
        const sendAt = el.scheduledEditTime?.value;
        if (!sendAt) {
            toast("Choose a new scheduled time first.", "error");
            return;
        }

        setLoading(el.btnSaveScheduled, true, "Saving...");
        try {
            const res = await api("PUT", `/api/scheduled-jobs/${currentScheduledJob.id}`, {
                send_at: new Date(sendAt).toISOString(),
            });
            if (res.success) {
                toast("Scheduled job updated.", "success");
                closeScheduledModal();
                loadScheduled();
                loadOperations();
            } else {
                toast(res.error || "Could not update scheduled job.", "error");
            }
        } catch (e) {
            console.error("Scheduled save error:", e);
            toast("Could not update scheduled job.", "error");
        }
        setLoading(el.btnSaveScheduled, false, '<i class="fas fa-save mr-2"></i>Save Changes');
    }

    window.cancelScheduled = async function(id) {
        if (!confirm("Cancel this scheduled job?")) return;
        try {
            const res = await api("POST", `/api/scheduled-jobs/${id}/cancel`);
            if (res.success) { toast("Scheduled job cancelled.", "info"); loadScheduled(); loadOperations(); }
            else { toast(res.error || "Cancel failed.", "error"); }
        } catch { toast("Network error.", "error"); }
    };

    window.deleteScheduled = async function(id) {
        if (!confirm("Delete this scheduled job?")) return;
        try {
            const res = await api("DELETE", `/api/scheduled-jobs/${id}`);
            if (res.success) { toast("Deleted.", "info"); loadScheduled(); loadOperations(); }
            else { toast(res.error || "Delete failed.", "error"); }
        } catch { toast("Network error.", "error"); }
    };

    function schedBadge(status) {
        const map = {
            pending:   { color: "blue",   icon: "clock",          label: "Pending" },
            running:   { color: "blue",   icon: "spinner fa-spin",label: "Firing" },
            sent:      { color: "green",  icon: "check",          label: "Sent" },
            failed:    { color: "red",    icon: "xmark",          label: "Failed" },
            cancelled: { color: "gray",   icon: "ban",            label: "Cancelled" },
        };
        const s = map[status] || { color: "gray", icon: "question", label: status };
        return `<span class="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full bg-${s.color}-600/20 text-${s.color}-300 border border-${s.color}-600/30">
            <i class="fas fa-${s.icon} mr-1 text-[10px]"></i>${s.label}
        </span>`;
    }

    function startCountdown() {
        stopCountdown();
        updateCountdowns();
        countdownTimer = setInterval(updateCountdowns, 1000);
    }

    function stopCountdown() {
        if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    }

    function updateCountdowns() {
        document.querySelectorAll(".sched-countdown").forEach(el => {
            const ts = parseFloat(el.dataset.ts) * 1000;
            const status = el.dataset.status;
            if (status !== "pending" || !ts) {
                if (status === "sent") el.textContent = "✓ Delivered";
                else if (status === "failed") el.textContent = "✗ Failed";
                else if (status === "cancelled") el.textContent = "— Cancelled";
                else if (status === "running") el.textContent = "⏳ Firing...";
                else el.textContent = "—";
                return;
            }
            const diff = Math.max(0, Math.floor((ts - Date.now()) / 1000));
            if (diff <= 0) {
                el.innerHTML = '<span class="text-green-400 animate-pulse">⏰ Firing now...</span>';
                return;
            }
            const h = Math.floor(diff / 3600);
            const m = Math.floor((diff % 3600) / 60);
            const s = diff % 60;
            let parts = [];
            if (h) parts.push(`${h}h`);
            if (m) parts.push(`${m}m`);
            parts.push(`${s}s`);
            el.innerHTML = `<span class="countdown-badge">${parts.join(" ")}</span>`;
        });
    }

    function renderScheduledPayloadPreview(job) {
        const payload = job.payload || {};
        const meta = [];
        if (job.type === "campaign") {
            meta.push(`<div><strong>Recipients:</strong> ${(payload.recipients || []).length}</div>`);
            meta.push(`<div><strong>Interval:</strong> ${payload.interval || "—"}s</div>`);
        } else {
            meta.push(`<div><strong>To:</strong> ${esc(payload.to_email || "—")}</div>`);
            if (payload.to_name) meta.push(`<div><strong>Name:</strong> ${esc(payload.to_name)}</div>`);
        }
        if (payload.from_email || payload.from_email_template) {
            meta.push(`<div><strong>From:</strong> ${esc(payload.from_email || payload.from_email_template)}</div>`);
        }
        if (payload.from_name || payload.from_name_template) {
            meta.push(`<div><strong>From name:</strong> ${esc(payload.from_name || payload.from_name_template)}</div>`);
        }

        const html = payload.html_content || "<p>No HTML content stored.</p>";
        return `
            <div class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-gray-800">${meta.join("")}</div>
                <div class="border-t border-gray-200 pt-4">${html}</div>
            </div>
        `;
    }

    function formatDatetimeLocalValue(timestampSeconds) {
        if (!timestampSeconds) return "";
        const date = new Date(timestampSeconds * 1000);
        const offsetMs = date.getTimezoneOffset() * 60000;
        return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
    }

    // ════════════════════════════════════════════════════════════════
    //  UTILITIES
    // ════════════════════════════════════════════════════════════════

    async function api(method, url, body) {
        const opts = { method, headers: { "Content-Type": "application/json" } };
        if (body) opts.body = JSON.stringify(body);
        const res = await fetch(url, opts);
        return res.json();
    }

    function setLoading(btn, loading, html) {
        if (!btn) return;
        if (!btn._origHTML) btn._origHTML = btn.innerHTML;
        if (loading) {
            btn.disabled = true;
            btn.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i>${html || "..."}`;
        } else {
            btn.disabled = false;
            btn.innerHTML = html || btn._origHTML;
        }
    }

    function esc(str) {
        const d = document.createElement("div");
        d.appendChild(document.createTextNode(str || ""));
        return d.innerHTML;
    }

    function fmtTime(date) {
        try { return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", hour12: true }); }
        catch { return ""; }
    }

    function fmtDuration(secs) {
        if (isNaN(secs) || secs < 0) return "—";
        secs = Math.round(secs);
        if (secs < 60) return `${secs}s`;
        const h = Math.floor(secs / 3600);
        const m = Math.floor((secs % 3600) / 60);
        const s = secs % 60;
        let parts = [];
        if (h) parts.push(`${h}h`);
        if (m) parts.push(`${m}m`);
        if (!h && s) parts.push(`${s}s`);
        return parts.join(" ") || "0s";
    }

    // ── Toast Notifications ────────────────────────────────────────

    function toast(msg, type = "info", duration = 5000) {
        const colors = {
            success: "bg-green-900/90 border-green-600 text-green-200",
            error:   "bg-red-900/90 border-red-600 text-red-200",
            warning: "bg-yellow-900/90 border-yellow-600 text-yellow-200",
            info:    "bg-blue-900/90 border-blue-600 text-blue-200",
        };
        const icons = { success: "check-circle", error: "circle-xmark", warning: "triangle-exclamation", info: "circle-info" };

        const div = document.createElement("div");
        div.className = `flex items-start p-3 rounded-lg border shadow-lg text-sm transition-all duration-300 opacity-0 translate-y-2 ${colors[type] || colors.info}`;
        div.innerHTML = `
            <i class="fas fa-${icons[type] || icons.info} mt-0.5 mr-2.5 flex-shrink-0"></i>
            <span class="flex-1">${esc(msg)}</span>
            <button class="ml-2 opacity-60 hover:opacity-100" aria-label="Dismiss"><i class="fas fa-xmark"></i></button>`;

        const dismiss = () => {
            div.style.opacity = "0";
            div.style.transform = "scale(0.95)";
            setTimeout(() => div.remove(), 300);
        };
        div.querySelector("button")?.addEventListener("click", dismiss);

        el.toasts?.appendChild(div);
        requestAnimationFrame(() => { div.style.opacity = "1"; div.style.transform = "translateY(0)"; });

        if (duration > 0) setTimeout(dismiss, duration);
    }

});
