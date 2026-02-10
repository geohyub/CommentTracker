/* ═══════════════════════════════════════════════════════
   Comment Tracker - Frontend JavaScript
   ═══════════════════════════════════════════════════════ */

// Sidebar toggle for mobile
document.addEventListener('DOMContentLoaded', function() {
    const toggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
        });
    }

    // File upload drag & drop
    const uploadArea = document.querySelector('.upload-area');
    const fileInput = document.getElementById('fileInput');

    if (uploadArea && fileInput) {
        uploadArea.addEventListener('click', function() {
            fileInput.click();
        });

        uploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', function() {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                handleFileSelect(e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener('change', function() {
            if (fileInput.files.length) {
                handleFileSelect(fileInput.files[0]);
            }
        });
    }
});

function handleFileSelect(file) {
    const uploadArea = document.querySelector('.upload-area');
    const fileName = document.getElementById('fileName');
    const csvFields = document.getElementById('csvFields');

    if (fileName) {
        fileName.textContent = file.name;
    }
    if (uploadArea) {
        uploadArea.innerHTML = `
            <i class="bi bi-file-earmark-check" style="color: #10b981;"></i>
            <h5>${file.name}</h5>
            <p class="text-muted mb-0">${(file.size / 1024).toFixed(1)} KB - Ready to import</p>
        `;
    }

    // Show CSV metadata fields if CSV file
    if (csvFields) {
        if (file.name.toLowerCase().endsWith('.csv')) {
            csvFields.style.display = 'block';
        } else {
            csvFields.style.display = 'none';
        }
    }
}

/* ─── Chart Helpers ───────────────────────────────────── */

// Default chart options
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            labels: {
                font: { family: 'Inter', size: 12 },
                usePointStyle: true,
                padding: 16
            }
        }
    }
};

// Color palette
const COLORS = {
    primary: '#4f6ef7',
    secondary: '#7c3aed',
    success: '#10b981',
    warning: '#f59e0b',
    danger: '#ef4444',
    info: '#06b6d4',
    categories: {
        'Technical': '#ef4444',
        'Typo': '#8b5cf6',
        'Readability': '#06b6d4',
        'FigTable': '#f59e0b',
        'Format': '#10b981',
        'Reference': '#6366f1'
    },
    severities: {
        'Major': '#ef4444',
        'Minor': '#4f6ef7'
    },
    statuses: {
        'Accepted': '#10b981',
        'Accepted (modified)': '#f59e0b',
        'Noted': '#06b6d4',
        'Rejected': '#ef4444'
    }
};

function createDoughnutChart(canvasId, labels, data, colors) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors || labels.map((_, i) => Object.values(COLORS.categories)[i]),
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            ...chartDefaults,
            cutout: '65%',
            plugins: {
                ...chartDefaults.plugins,
                legend: {
                    ...chartDefaults.plugins.legend,
                    position: 'bottom'
                }
            }
        }
    });
}

function createBarChart(canvasId, labels, datasets, options) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            ...chartDefaults,
            ...options,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: '#f1f5f9' },
                    ticks: { font: { family: 'Inter', size: 11 } }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { family: 'Inter', size: 11 } }
                }
            }
        }
    });
}

function createLineChart(canvasId, labels, datasets, options) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            ...chartDefaults,
            ...options,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: '#f1f5f9' },
                    ticks: { font: { family: 'Inter', size: 11 } }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { family: 'Inter', size: 11 } }
                }
            }
        }
    });
}

/* ─── Utility ─────────────────────────────────────────── */

function getSeverityBadge(severity) {
    const cls = severity === 'Major' ? 'badge-major' : 'badge-minor';
    return `<span class="badge-severity ${cls}">${severity}</span>`;
}

function getStatusBadge(status) {
    let cls = 'badge-accepted';
    if (status === 'Accepted (modified)') cls = 'badge-modified';
    else if (status === 'Noted') cls = 'badge-noted';
    else if (status === 'Rejected') cls = 'badge-rejected';
    return `<span class="badge-status ${cls}">${status}</span>`;
}

function getReductionBadge(value) {
    if (value === null || value === undefined) return '<span class="text-muted">N/A</span>';
    let cls = 'reduction-bad';
    if (value >= 70) cls = 'reduction-good';
    else if (value >= 40) cls = 'reduction-ok';
    const arrow = value >= 0 ? '&#9660;' : '&#9650;';
    return `<span class="reduction-badge ${cls}">${arrow} ${value}%</span>`;
}
