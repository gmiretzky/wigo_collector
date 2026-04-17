async function fetchData() {
    try {
        const summaryResponse = await fetch('/api/dashboard/summary');
        const summaryData = await summaryResponse.json();
        renderMachines(summaryData);

        const aiResponse = await fetch('/api/dashboard/ai-insights');
        const aiData = await aiResponse.json();
        renderAIInsights(aiData);

        const logStatsResponse = await fetch('/api/dashboard/logs/stats');
        const logStatsData = await logStatsResponse.json();
        renderLogStats(logStatsData);
    } catch (error) {
        console.error('Error fetching data:', error);
    }
}

function renderLogStats(data) {
    const container = document.getElementById('log-stats-container');
    container.innerHTML = '';

    // Total Stats Card
    const totalCard = document.createElement('div');
    totalCard.className = 'card';
    totalCard.innerHTML = `
        <h3>Global Log Stats <span class="status-badge status-ok">AGGREGATED</span></h3>
        <div class="metrics-list">
            <div class="metric-item">
                <span class="metric-label">Total Entries</span>
                <span class="metric-value">${data.total_count}</span>
            </div>
            <div class="metric-item">
                <span class="metric-label">Sources</span>
                <span class="metric-value">${Object.keys(data.sources).join(', ') || 'None'}</span>
            </div>
        </div>
    `;
    container.appendChild(totalCard);

    // Per Machine Stats
    data.machines.forEach(m => {
        const mCard = document.createElement('div');
        mCard.className = 'card';
        const sizeKB = (m.size_bytes / 1024).toFixed(2);
        mCard.innerHTML = `
            <h3>${m.name} Logs <span class="status-badge status-ok">STATS</span></h3>
            <div class="metrics-list">
                <div class="metric-item">
                    <span class="metric-label">Count</span>
                    <span class="metric-value">${m.count}</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Estimated Size</span>
                    <span class="metric-value">${sizeKB} KB</span>
                </div>
            </div>
        `;
        container.appendChild(mCard);
    });
}

function renderMachines(machines) {
    const container = document.getElementById('machines-container');
    container.innerHTML = '';

    machines.forEach(machine => {
        const card = document.createElement('div');
        card.className = 'card';
        
        let metricsHtml = '';
        machine.latest_metrics.forEach(m => {
            const statusClass = `status-${m.status || 'ok'}`;
            metricsHtml += `
                <div class="metric-item">
                    <span class="metric-label">${m.object}</span>
                    <span class="metric-value ${statusClass}">${m.value}${m.unit}</span>
                </div>
            `;
        });

        const logsHtml = machine.recent_logs.map(log => `<div class="log-entry">${log}</div>`).join('');

        card.innerHTML = `
            <h3>${machine.name} <span class="status-badge status-ok">ONLINE</span></h3>
            <div class="metrics-list">
                ${metricsHtml}
            </div>
            <div class="log-viewer">
                ${logsHtml || '<div class="log-entry">No recent logs</div>'}
            </div>
        `;
        container.appendChild(card);
    });
}

function renderAIInsights(insights) {
    const nocInsight = insights.find(i => i.analysis_type === 'NOC');
    const siemInsight = insights.find(i => i.analysis_type === 'SIEM');

    if (nocInsight) {
        document.getElementById('noc-insight').innerText = nocInsight.summary;
    }
    if (siemInsight) {
        document.getElementById('siem-insight').innerText = siemInsight.summary;
    }
}

// Settings Modal Logic
const modal = document.getElementById('settings-modal');
const configBtn = document.getElementById('config-btn');
const closeBtns = document.querySelectorAll('.close-btn');
const settingsForm = document.getElementById('settings-form');
const aiProviderSelect = document.getElementById('ai_provider');

configBtn.onclick = async (e) => {
    e.preventDefault();
    await loadSettings();
    modal.style.display = 'block';
};

closeBtns.forEach(btn => {
    btn.onclick = () => {
        modal.style.display = 'none';
    };
});

window.onclick = (event) => {
    if (event.target == modal) {
        modal.style.display = 'none';
    }
};

aiProviderSelect.onchange = (e) => {
    const provider = e.target.value;
    document.getElementById('gemini-settings').style.display = provider === 'gemini' ? 'block' : 'none';
    document.getElementById('ollama-settings').style.display = provider === 'ollama' ? 'block' : 'none';
};

async function loadSettings() {
    try {
        const response = await fetch('/api/config/');
        const config = await response.json();

        // Populate form
        document.getElementById('ai_provider').value = config.ai?.provider || 'gemini';
        document.getElementById('gemini_api_key').value = config.ai?.gemini?.api_key || '';
        document.getElementById('ollama_url').value = config.ai?.ollama?.base_url || '';
        
        document.getElementById('noc_interval').value = config.scheduler?.noc_interval_hours || 4;
        document.getElementById('siem_interval').value = config.scheduler?.siem_interval_hours || 4;
        
        document.getElementById('pushover_enabled').checked = config.webhooks?.pushover?.enabled || false;
        document.getElementById('pushover_token').value = config.webhooks?.pushover?.token || '';
        document.getElementById('pushover_user').value = config.webhooks?.pushover?.user || '';

        document.getElementById('retention_days').value = config.maintenance?.retention_days || 7;

        // Trigger AI provider toggle
        aiProviderSelect.dispatchEvent(new Event('change'));

        // Load Syslog Mappings
        loadSyslogMappings();
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

async function loadSyslogMappings() {
    try {
        const response = await fetch('/api/config/syslog-mappings');
        const mappings = await response.json();
        const list = document.getElementById('syslog-mappings-list');
        list.innerHTML = mappings.map(m => `
            <div class="metric-item" style="padding: 0.5rem; background: rgba(255,255,255,0.05); border-radius: 0.5rem; margin-bottom: 0.5rem;">
                <span>${m.ip_address} &rarr; ${m.machine_name}</span>
            </div>
        `).join('') || '<p style="color: var(--text-secondary); font-size: 0.8rem;">No mappings configured.</p>';
    } catch (error) {
        console.error('Error loading mappings:', error);
    }
}

document.getElementById('add-mapping-btn').onclick = async () => {
    const ip = document.getElementById('new_syslog_ip').value;
    const name = document.getElementById('new_syslog_name').value;
    
    if (!ip || !name) return alert('Please fill both fields');

    try {
        const response = await fetch('/api/config/syslog-mappings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip_address: ip, machine_name: name })
        });
        if (response.ok) {
            document.getElementById('new_syslog_ip').value = '';
            document.getElementById('new_syslog_name').value = '';
            loadSyslogMappings();
        }
    } catch (error) {
        console.error('Error saving mapping:', error);
    }
};

settingsForm.onsubmit = async (e) => {
    e.preventDefault();
    
    // Fetch current config first to preserve other fields (like thresholds)
    const currentConfigResponse = await fetch('/api/config/');
    let config = await currentConfigResponse.json();

    // Update with form values
    config.ai = config.ai || {};
    config.ai.provider = document.getElementById('ai_provider').value;
    config.ai.gemini = config.ai.gemini || {};
    config.ai.gemini.api_key = document.getElementById('gemini_api_key').value;
    config.ai.ollama = config.ai.ollama || {};
    config.ai.ollama.base_url = document.getElementById('ollama_url').value;

    config.scheduler = config.scheduler || {};
    config.scheduler.noc_interval_hours = parseInt(document.getElementById('noc_interval').value);
    config.scheduler.siem_interval_hours = parseInt(document.getElementById('siem_interval').value);

    config.webhooks = config.webhooks || {};
    config.webhooks.pushover = config.webhooks.pushover || {};
    config.webhooks.pushover.enabled = document.getElementById('pushover_enabled').checked;
    config.webhooks.pushover.token = document.getElementById('pushover_token').value;
    config.webhooks.pushover.user = document.getElementById('pushover_user').value;

    config.maintenance = config.maintenance || {};
    config.maintenance.retention_days = parseInt(document.getElementById('retention_days').value);

    try {
        const response = await fetch('/api/config/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        if (response.ok) {
            alert('Settings saved successfully!');
            modal.style.display = 'none';
        } else {
            alert('Error saving settings.');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        alert('Error connecting to server.');
    }
};

document.getElementById('purge-btn').onclick = async () => {
    if (!confirm('Are you sure you want to purge old data? This cannot be undone.')) return;
    
    try {
        const response = await fetch('/api/maintenance/purge', { method: 'POST' });
        const data = await response.json();
        alert(data.message);
        fetchData(); // Refresh dashboard
    } catch (error) {
        alert('Purge failed');
    }
};

document.getElementById('process-ai-btn').onclick = async () => {
    const btn = document.getElementById('process-ai-btn');
    btn.disabled = true;
    btn.innerText = 'Processing...';
    
    try {
        await fetch('/api/maintenance/ai-process/noc', { method: 'POST' });
        await fetch('/api/maintenance/ai-process/siem', { method: 'POST' });
        alert('AI Analysis triggered successfully!');
        fetchData();
    } catch (error) {
        alert('AI Analysis failed');
    } finally {
        btn.disabled = false;
        btn.innerText = 'Trigger AI Analysis';
    }
};

document.getElementById('full-cycle-btn').onclick = async () => {
    if (!confirm('Run full AI analysis and purge processed data?')) return;
    
    const btn = document.getElementById('full-cycle-btn');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = 'Analyzing...';
    
    try {
        const response = await fetch('/api/maintenance/full-cycle-ai', { method: 'POST' });
        const data = await response.json();
        
        if (response.ok) {
            alert('Analysis complete! Data has been purged and notifications sent.');
            fetchData(); // Refresh everything
        } else {
            alert('Error: ' + data.detail);
        }
    } catch (error) {
        console.error('Full cycle failed:', error);
        alert('Network error or server failed.');
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
};

// Initial fetch
fetchData();

// Refresh every 30 seconds
setInterval(fetchData, 30000);
