// Application State
const state = {
    page: 1,
    limit: 20,
    sortBy: "rank",
    order: "asc",
    search: "",
    minExp: null,
    maxExp: null,
    workMode: "all",
    excludeHoneypots: true,
    totalCount: 0
};

// DOM Elements
const elements = {
    // Stats
    statTotalPool: document.getElementById("stat-total-pool"),
    statValidCount: document.getElementById("stat-valid-count"),
    statHoneypotCount: document.getElementById("stat-honeypot-count"),
    statRelocationRate: document.getElementById("stat-relocation-rate"),
    
    // Filters & Inputs
    searchInput: document.getElementById("search-input"),
    workModeFilter: document.getElementById("work-mode-filter"),
    sortSelect: document.getElementById("sort-select"),
    orderSelect: document.getElementById("order-select"),
    minExpInput: document.getElementById("min-exp-input"),
    maxExpInput: document.getElementById("max-exp-input"),
    honeypotToggle: document.getElementById("honeypot-toggle"),
    btnResetFilters: document.getElementById("btn-reset-filters"),
    
    // Candidates Area
    resultsCountText: document.getElementById("results-count-text"),
    candidatesLoader: document.getElementById("candidates-loader"),
    candidatesContainer: document.getElementById("candidates-container"),
    
    // Pagination
    paginationContainer: document.getElementById("pagination-container"),
    btnPrevPage: document.getElementById("btn-prev-page"),
    btnNextPage: document.getElementById("btn-next-page"),
    pageInfoText: document.getElementById("page-info-text"),
    
    // Modals
    candidateModal: document.getElementById("candidate-modal"),
    btnCloseModal: document.getElementById("btn-close-modal"),
    modalBodyContent: document.getElementById("modal-body-content"),
    
    btnRunRanker: document.getElementById("btn-run-ranker"),
    submissionModal: document.getElementById("submission-modal"),
    btnCloseSubmissionModal: document.getElementById("btn-close-submission-modal"),
    btnPipelineRun: document.getElementById("btn-pipeline-run"),
    pipelineOutputContainer: document.getElementById("pipeline-output-container"),
    pipelineConsoleLog: document.getElementById("pipeline-console-log"),
    
    // Menu Links
    menuDashboard: document.getElementById("menu-dashboard"),
    menuCandidatesList: document.getElementById("menu-candidates-list"),
    menuSubmission: document.getElementById("menu-submission")
};

// API Fetch Functions
async function fetchStats() {
    try {
        const res = await fetch("/api/stats");
        const data = await res.json();
        
        elements.statTotalPool.textContent = data.total_pool.toLocaleString();
        elements.statValidCount.textContent = data.valid_count.toLocaleString();
        elements.statHoneypotCount.textContent = data.honeypot_count.toLocaleString();
        elements.statRelocationRate.textContent = `${data.relocation_rate}%`;
    } catch (err) {
        console.error("Failed to fetch stats:", err);
    }
}

async function fetchCandidates() {
    elements.candidatesLoader.style.display = "flex";
    elements.candidatesContainer.style.display = "none";
    elements.paginationContainer.style.display = "none";
    
    try {
        const queryParams = new URLSearchParams({
            page: state.page,
            limit: state.limit,
            sort_by: state.sortBy,
            order: state.order,
            exclude_honeypots: state.excludeHoneypots
        });
        
        if (state.search) queryParams.append("search", state.search);
        if (state.workMode && state.workMode !== "all") queryParams.append("work_mode", state.workMode);
        if (state.minExp !== null && !isNaN(state.minExp)) queryParams.append("min_exp", state.minExp);
        if (state.maxExp !== null && !isNaN(state.maxExp)) queryParams.append("max_exp", state.maxExp);
        
        const res = await fetch(`/api/candidates?${queryParams.toString()}`);
        const data = await res.json();
        
        state.totalCount = data.total;
        elements.resultsCountText.textContent = `Showing ${data.total.toLocaleString()} candidates`;
        
        renderCandidatesGrid(data.candidates);
        renderPagination();
    } catch (err) {
        console.error("Failed to fetch candidates:", err);
        elements.candidatesContainer.innerHTML = `
            <div class="card error-card" style="grid-column: 1/-1; text-align: center; color: var(--danger);">
                <i class="fa-solid fa-triangle-exclamation" style="font-size: 2rem; margin-bottom: 0.5rem;"></i>
                <p>Failed to load candidates. Please make sure the FastAPI server is running.</p>
            </div>
        `;
        elements.candidatesContainer.style.display = "grid";
    } finally {
        elements.candidatesLoader.style.display = "none";
    }
}

async function fetchCandidateDetail(id) {
    try {
        const res = await fetch(`/api/candidates/${id}`);
        const data = await res.json();
        renderCandidateModal(data);
        elements.candidateModal.classList.add("active");
    } catch (err) {
        console.error("Failed to fetch candidate details:", err);
    }
}

// Render Functions
function renderCandidatesGrid(candidates) {
    elements.candidatesContainer.innerHTML = "";
    
    if (candidates.length === 0) {
        elements.candidatesContainer.innerHTML = `
            <div class="card" style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-secondary);">
                <i class="fa-solid fa-folder-open" style="font-size: 2.5rem; margin-bottom: 0.75rem; color: var(--text-muted);"></i>
                <p>No candidates match your current search queries or filters.</p>
            </div>
        `;
        elements.candidatesContainer.style.display = "grid";
        return;
    }
    
    candidates.forEach((c) => {
        const card = document.createElement("div");
        card.className = `card candidate-card ${c.is_honeypot ? 'honeypot-border' : ''}`;
        
        // Rank Badge
        let rankClass = "rank-standard";
        let rankText = c.is_honeypot ? "Honeypot" : `Rank #${c.rank}`;
        if (c.is_honeypot) {
            rankClass = "rank-honeypot";
        } else if (c.rank === 1) {
            rankClass = "rank-top1";
            rankText = `<i class="fa-solid fa-trophy"></i> Rank #1`;
        } else if (c.rank <= 3) {
            rankClass = "rank-top3";
            rankText = `<i class="fa-solid fa-medal"></i> Rank #${c.rank}`;
        }
        
        // Score Badge
        let scoreClass = "score-mid";
        if (c.is_honeypot) {
            scoreClass = "score-low";
        } else if (c.score >= 0.85) {
            scoreClass = "score-high";
        } else if (c.score < 0.6) {
            scoreClass = "score-low";
        }
        
        const displayScore = c.is_honeypot ? "0%" : `${Math.round(c.score * 100)}%`;
        
        // Header Row
        const badgeRow = `
            <div class="candidate-badge-row">
                <span class="badge ${rankClass}">${rankText}</span>
                <span class="score-badge ${scoreClass}">${displayScore} Match</span>
            </div>
        `;
        
        // Info Row
        const infoRow = `
            <div class="candidate-main-info">
                <span class="candidate-name">${c.name}</span>
                <span class="candidate-title">${c.current_title || "Senior Engineer"}</span>
                <span class="candidate-company-meta">${c.current_company || "Product Company"} &bull; ${c.years_of_experience} Yrs Exp</span>
            </div>
        `;
        
        // Headline
        const headline = `
            <p class="candidate-desc">${c.headline || "Applied machine learning engineer specializing in NLP and search ranking systems."}</p>
        `;
        
        // Extra meta footer
        const modeLabel = c.preferred_work_mode ? c.preferred_work_mode.toUpperCase() : "HYBRID";
        const noticeLabel = c.notice_period_days !== null ? `${c.notice_period_days}d Notice` : "30d Notice";
        const locationLabel = c.location ? c.location.split(",")[0] : "Pune";
        
        const footer = `
            <div class="candidate-footer">
                <span class="candidate-footer-item"><i class="fa-solid fa-briefcase"></i> ${modeLabel}</span>
                <span class="candidate-footer-item"><i class="fa-solid fa-clock"></i> ${noticeLabel}</span>
                <span class="candidate-footer-item"><i class="fa-solid fa-location-dot"></i> ${locationLabel}</span>
            </div>
        `;
        
        card.innerHTML = `
            ${badgeRow}
            ${infoRow}
            ${headline}
            <button class="btn btn-secondary btn-view-profile" data-id="${c.candidate_id}" style="width: 100%; margin-top: auto;">
                <i class="fa-solid fa-user"></i> View Profile
            </button>
            ${footer}
        `;
        
        elements.candidatesContainer.appendChild(card);
    });
    
    // Attach details click listeners
    const viewButtons = elements.candidatesContainer.querySelectorAll(".btn-view-profile");
    viewButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const id = btn.getAttribute("data-id");
            fetchCandidateDetail(id);
        });
    });
    
    elements.candidatesContainer.style.display = "grid";
}

function renderPagination() {
    const totalPages = Math.ceil(state.totalCount / state.limit) || 1;
    elements.pageInfoText.textContent = `Page ${state.page} of ${totalPages}`;
    
    elements.btnPrevPage.disabled = (state.page === 1);
    elements.btnNextPage.disabled = (state.page >= totalPages);
    
    elements.paginationContainer.style.display = "flex";
}

function renderCandidateModal(c) {
    const p = c.profile;
    const sigs = c.redrob_signals;
    
    // Header
    const modeBadge = sigs.preferred_work_mode ? sigs.preferred_work_mode.toUpperCase() : "HYBRID";
    const relocateText = sigs.willing_to_relocate ? "Willing to relocate" : "Not open to relocation";
    const relocateIcon = sigs.willing_to_relocate ? "fa-circle-check text-green" : "fa-circle-xmark text-muted";
    
    let headerHTML = `
        <div class="candidate-detail-header">
            <div class="candidate-detail-intro">
                <h2>${p.anonymized_name}</h2>
                <div class="headline">${p.headline}</div>
                <div class="metadata-meta">
                    <span><i class="fa-solid fa-location-dot"></i> ${p.location}, ${p.country || "India"}</span>
                    <span><i class="fa-solid fa-briefcase"></i> ${p.years_of_experience} Years Experience</span>
                    <span><i class="fa-solid fa-clock"></i> ${sigs.notice_period_days} Days Notice</span>
                </div>
            </div>
            <div style="text-align: right;">
                <div class="score-badge ${c.score >= 0.85 ? 'score-high' : 'score-mid'}" style="font-size: 1.15rem; padding: 0.5rem 1rem;">
                    ${c.is_honeypot ? '0%' : Math.round(c.score * 100)}% Match Score
                </div>
                <div class="subtitle" style="margin-top: 0.5rem;">Rank #${c.rank || "N/A"}</div>
            </div>
        </div>
    `;
    
    // Reasoning card
    let reasoningHTML = "";
    if (c.is_honeypot) {
        reasoningHTML = `
            <div class="reasoning-box" style="background: var(--danger-light); border-color: rgba(239, 68, 68, 0.2);">
                <h4 style="color: var(--danger);"><i class="fa-solid fa-triangle-exclamation"></i> Flagged Honeypot</h4>
                <p><strong>Reason:</strong> ${c.honeypot_reason || "Inconsistent candidate data detected."}</p>
            </div>
        `;
    } else {
        reasoningHTML = `
            <div class="reasoning-box">
                <h4><i class="fa-solid fa-wand-magic-sparkles"></i> Gravity Fit Assessment</h4>
                <p>${c.reasoning}</p>
            </div>
        `;
    }
    
    // Career History Timeline
    let careerHTML = '<div class="timeline">';
    if (c.career_history && c.career_history.length > 0) {
        c.career_history.forEach(job => {
            const endDateText = job.is_current ? "Present" : job.end_date;
            careerHTML += `
                <div class="timeline-item animate-fade-in">
                    <div class="timeline-marker"></div>
                    <div class="timeline-header">
                        <div>
                            <span class="timeline-role">${job.title}</span>
                            <div class="timeline-company">${job.company} &bull; ${job.industry} &bull; Size: ${job.company_size}</div>
                        </div>
                        <span class="timeline-date">${job.start_date} to ${endDateText} (${job.duration_months}m)</span>
                    </div>
                    <p class="timeline-desc">${job.description}</p>
                </div>
            `;
        });
    } else {
        careerHTML += '<p class="text-muted">No career history records reported.</p>';
    }
    careerHTML += '</div>';
    
    // Skills lists
    let skillsHTML = '<div class="skills-list-detail">';
    if (c.skills && c.skills.length > 0) {
        c.skills.forEach(s => {
            const isTarget = s.name.toLowerCase() in {
                "pinecone":1,"milvus":1,"weaviate":1,"qdrant":1,"faiss":1,"elasticsearch":1,"opensearch":1,
                "embeddings":1,"sentence transformers":1,"nlp":1,"transformers":1,"pytorch":1,"llama":1,
                "langchain":1,"llamaindex":1,"rag":1,"fine-tuning":1,"lora":1,"qlora":1,"peft":1,"python":1,
                "ndcg":1,"map":1,"mrr":1
            };
            
            skillsHTML += `
                <div class="skill-row-detail">
                    <span class="skill-name-detail">${s.name} ${isTarget ? '<i class="fa-solid fa-star text-blue" style="font-size: 0.7rem;" title="Target JD Skill"></i>':''}</span>
                    <div class="skill-meta-detail">
                        <span class="proficiency-badge prof-${s.proficiency}">${s.proficiency}</span>
                        <span class="skill-duration-detail">${s.duration_months} months</span>
                    </div>
                </div>
            `;
        });
    } else {
        skillsHTML += '<p class="text-muted">No skills listed.</p>';
    }
    skillsHTML += '</div>';
    
    // Redrob activity signals widget
    const responseRatePercent = Math.round(sigs.recruiter_response_rate * 100);
    const responseTimeText = sigs.avg_response_time_hours > 0 ? `${sigs.avg_response_time_hours} hrs` : "N/A";
    const githubText = sigs.github_activity_score !== -1 ? `${sigs.github_activity_score}/100` : "Not Linked";
    const salaryRangeText = sigs.expected_salary_range_inr_lpa ? `₹${sigs.expected_salary_range_inr_lpa.min}L - ₹${sigs.expected_salary_range_inr_lpa.max}L` : "Negotiable";
    
    let signalsHTML = `
        <div class="signals-grid-detail">
            <div class="signal-widget-detail">
                <span class="signal-widget-label">Response Rate</span>
                <span class="signal-widget-value">${responseRatePercent}%</span>
                <div style="width: 100%; height: 6px; background-color: var(--border-color); border-radius: 3px; margin-top: 0.35rem; overflow: hidden;">
                    <div style="width: ${responseRatePercent}%; height: 100%; background-color: var(--success); border-radius: 3px;"></div>
                </div>
            </div>
            <div class="signal-widget-detail">
                <span class="signal-widget-label">Avg Response Time</span>
                <span class="signal-widget-value">${responseTimeText}</span>
            </div>
            <div class="signal-widget-detail">
                <span class="signal-widget-label">GitHub Activity</span>
                <span class="signal-widget-value"><i class="fa-brands fa-github"></i> ${githubText}</span>
            </div>
            <div class="signal-widget-detail">
                <span class="signal-widget-label">Expected Salary (INR)</span>
                <span class="signal-widget-value">${salaryRangeText}</span>
            </div>
            <div class="signal-widget-detail">
                <span class="signal-widget-label">Work Preference</span>
                <span class="signal-widget-value"><i class="fa-solid fa-building-user text-purple"></i> ${modeBadge}</span>
            </div>
            <div class="signal-widget-detail">
                <span class="signal-widget-label">Relocation status</span>
                <span class="signal-widget-value"><i class="fa-solid ${relocateIcon}"></i> <span style="font-size: 0.8rem; font-weight: 500;">${relocateText}</span></span>
            </div>
        </div>
    `;
    
    // Core detail template
    elements.modalBodyContent.innerHTML = `
        ${headerHTML}
        ${reasoningHTML}
        <div class="detail-section-grid">
            <div class="detail-column">
                <div class="detail-group">
                    <h3>Experience Timeline</h3>
                    ${careerHTML}
                </div>
            </div>
            <div class="detail-column">
                <div class="detail-group">
                    <h3>Redrob Ecosystem Signals</h3>
                    ${signalsHTML}
                </div>
                <div class="detail-group">
                    <h3>Skills Inventory</h3>
                    ${skillsHTML}
                </div>
            </div>
        </div>
    `;
}

// Filter Event Listeners
function registerEventListeners() {
    // Search input debouncer
    let searchTimeout;
    elements.searchInput.addEventListener("input", (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            state.search = e.target.value.trim();
            state.page = 1;
            fetchCandidates();
        }, 350);
    });
    
    // Work mode filter
    elements.workModeFilter.addEventListener("change", (e) => {
        state.workMode = e.target.value;
        state.page = 1;
        fetchCandidates();
    });
    
    // Sorting
    elements.sortSelect.addEventListener("change", (e) => {
        state.sortBy = e.target.value;
        state.page = 1;
        fetchCandidates();
    });
    
    elements.orderSelect.addEventListener("change", (e) => {
        state.order = e.target.value;
        state.page = 1;
        fetchCandidates();
    });
    
    // Experience Bounds
    elements.minExpInput.addEventListener("input", (e) => {
        state.minExp = e.target.value ? parseFloat(e.target.value) : null;
        state.page = 1;
        fetchCandidates();
    });
    
    elements.maxExpInput.addEventListener("input", (e) => {
        state.maxExp = e.target.value ? parseFloat(e.target.value) : null;
        state.page = 1;
        fetchCandidates();
    });
    
    // Honeypot Toggle
    elements.honeypotToggle.addEventListener("change", (e) => {
        state.excludeHoneypots = e.target.checked;
        state.page = 1;
        fetchCandidates();
    });
    
    // Reset Filters
    elements.btnResetFilters.addEventListener("click", () => {
        elements.searchInput.value = "";
        elements.workModeFilter.value = "all";
        elements.sortSelect.value = "rank";
        elements.orderSelect.value = "asc";
        elements.minExpInput.value = "";
        elements.maxExpInput.value = "";
        elements.honeypotToggle.checked = true;
        
        state.search = "";
        state.workMode = "all";
        state.sortBy = "rank";
        state.order = "asc";
        state.minExp = null;
        state.maxExp = null;
        state.excludeHoneypots = true;
        state.page = 1;
        
        fetchCandidates();
    });
    
    // Pagination Clicks
    elements.btnPrevPage.addEventListener("click", () => {
        if (state.page > 1) {
            state.page--;
            fetchCandidates();
            elements.candidatesContainer.scrollIntoView({ behavior: 'smooth' });
        }
    });
    
    elements.btnNextPage.addEventListener("click", () => {
        const totalPages = Math.ceil(state.totalCount / state.limit);
        if (state.page < totalPages) {
            state.page++;
            fetchCandidates();
            elements.candidatesContainer.scrollIntoView({ behavior: 'smooth' });
        }
    });
    
    // Modal toggle close
    elements.btnCloseModal.addEventListener("click", () => {
        elements.candidateModal.classList.remove("active");
    });
    
    // Click outside to close modal
    window.addEventListener("click", (e) => {
        if (e.target === elements.candidateModal) {
            elements.candidateModal.classList.remove("active");
        }
        if (e.target === elements.submissionModal) {
            elements.submissionModal.classList.remove("active");
        }
    });
    
    // Menu navigation links
    elements.menuDashboard.addEventListener("click", (e) => {
        e.preventDefault();
        elements.menuDashboard.classList.add("active");
        elements.menuCandidatesList.classList.remove("active");
        
        // Reset search to standard recommended top candidates
        elements.btnResetFilters.click();
    });
    
    elements.menuCandidatesList.addEventListener("click", (e) => {
        e.preventDefault();
        elements.menuCandidatesList.classList.add("active");
        elements.menuDashboard.classList.remove("active");
        
        // Switch to search mode sorting by experience
        elements.sortSelect.value = "experience";
        state.sortBy = "experience";
        state.page = 1;
        fetchCandidates();
    });
    
    // Run Pipeline buttons
    elements.menuSubmission.addEventListener("click", (e) => {
        e.preventDefault();
        elements.submissionModal.classList.add("active");
    });
    
    elements.btnRunRanker.addEventListener("click", () => {
        elements.submissionModal.classList.add("active");
    });
    
    elements.btnCloseSubmissionModal.addEventListener("click", () => {
        elements.submissionModal.classList.remove("active");
    });
    
    // Execute submission build pipeline button
    elements.btnPipelineRun.addEventListener("click", async () => {
        elements.btnPipelineRun.disabled = true;
        elements.btnPipelineRun.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing Pool...`;
        
        const rankStep = document.getElementById("step-rank");
        const csvStep = document.getElementById("step-csv");
        const validateStep = document.getElementById("step-validate");
        
        // Reset steps UI
        [rankStep, csvStep, validateStep].forEach(s => {
            s.className = "step";
        });
        
        elements.pipelineOutputContainer.style.display = "block";
        elements.pipelineConsoleLog.textContent = "Launching pipeline subprocess...\n";
        
        try {
            // Step 1: Run heuristics
            rankStep.classList.add("active");
            elements.pipelineConsoleLog.textContent += "Stage 1: Scanning pool & scoring ML features...\n";
            
            const res = await fetch("/api/generate", { method: "POST" });
            const data = await res.json();
            
            if (data.success) {
                rankStep.className = "step success";
                csvStep.className = "step success";
                
                elements.pipelineConsoleLog.textContent += data.ranker_output;
                
                // Step 3: Validate
                validateStep.classList.add("active");
                elements.pipelineConsoleLog.textContent += "\nStage 3: Running challenge validate_submission.py...\n";
                elements.pipelineConsoleLog.textContent += data.validator_output;
                
                if (data.is_valid) {
                    validateStep.className = "step success";
                    elements.pipelineConsoleLog.textContent += "\nValidation completed! submission.csv is 100% compliant with challenge spec.\n";
                    
                    // Auto-close modal after successful pipeline run so recruiter can see candidates
                    setTimeout(() => {
                        elements.submissionModal.classList.remove("active");
                    }, 1800);
                } else {
                    validateStep.className = "step error";
                    elements.pipelineConsoleLog.textContent += "\nValidation failed. Check specs formatting rules.\n";
                }
            } else {
                rankStep.className = "step error";
                elements.pipelineConsoleLog.textContent += `Error executing ranker: ${data.error}\n`;
            }
        } catch (err) {
            rankStep.className = "step error";
            elements.pipelineConsoleLog.textContent += `Subprocess error: ${err.message}\n`;
        } finally {
            elements.btnPipelineRun.disabled = false;
            elements.btnPipelineRun.innerHTML = `<i class="fa-solid fa-play"></i> Run Pipeline and Validate`;
            
            // Reload stats and current grid
            fetchStats();
            fetchCandidates();
        }
    });
}

// Initial Boot
function init() {
    registerEventListeners();
    fetchStats();
    fetchCandidates();
}

window.addEventListener("DOMContentLoaded", init);
