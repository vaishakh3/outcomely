/**
 * Outcomely - Frontend JavaScript
 * Handles API calls and dynamic content rendering
 */

const API_BASE = '/api';

// Utility Functions
function formatPercent(value) {
    if (value === null || value === undefined || value === 0) return '—';
    return `${(value * 100).toFixed(1)}%`;
}

function getAccuracyClass(score) {
    if (score >= 0.7) return 'high';
    if (score >= 0.5) return 'medium';
    return 'low';
}

function getRankClass(rank) {
    if (rank === 1) return 'rank-1';
    if (rank === 2) return 'rank-2';
    if (rank === 3) return 'rank-3';
    return 'rank-other';
}

function getInitials(name) {
    return name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
}

function formatDate(dateStr) {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-IN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// API Calls
async function fetchAPI(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`);
        if (!response.ok) throw new Error('API request failed');
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        return null;
    }
}

// Leaderboard Page
async function loadLeaderboard() {
    const tbody = document.getElementById('leaderboard-body');
    if (!tbody) return;

    // Load stats
    loadStats();

    // Fetch leaderboard data
    const data = await fetchAPI('/leaderboard');

    if (!data || !data.leaderboard || data.leaderboard.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6">
                    <div class="empty-state">
                        <div class="empty-state-icon">📊</div>
                        <h3>No Data Yet</h3>
                        <p>Run the data collection pipeline to populate the leaderboard.</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = data.leaderboard.map((creator, index) => {
        const rank = index + 1;
        const accuracy = creator.accuracy_score || 0;
        const accuracyClass = getAccuracyClass(accuracy);
        const rankClass = getRankClass(rank);

        return `
            <tr class="fade-in" style="animation-delay: ${index * 0.05}s">
                <td class="col-rank">
                    <span class="rank-badge ${rankClass}">${rank}</span>
                </td>
                <td>
                    <div class="creator-cell">
                        <div class="creator-avatar">${getInitials(creator.name)}</div>
                        <div class="creator-info">
                            <h3>${creator.name}</h3>
                            <p>${creator.description || 'Finance YouTuber'}</p>
                        </div>
                    </div>
                </td>
                <td class="col-accuracy">
                    <div class="accuracy-display">
                        <span class="accuracy-value ${accuracyClass}">${formatPercent(accuracy)}</span>
                        <div class="accuracy-bar">
                            <div class="accuracy-bar-fill ${accuracyClass}" 
                                 style="width: ${accuracy * 100}%"></div>
                        </div>
                    </div>
                </td>
                <td class="col-predictions">${creator.total_predictions || 0}</td>
                <td class="col-videos">${creator.video_count || 0}</td>
                <td class="col-action">
                    <a href="/creator/${creator.slug}" class="view-btn">
                        View Details →
                    </a>
                </td>
            </tr>
        `;
    }).join('');
}

async function loadStats() {
    const data = await fetchAPI('/stats');

    if (data) {
        const setStatValue = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        };

        setStatValue('stat-creators', data.total_creators || 0);
        setStatValue('stat-predictions', data.total_predictions || 0);
        setStatValue('stat-verified', data.verified_predictions || 0);
        setStatValue('stat-avg-accuracy', formatPercent(data.average_accuracy));
    }
}

// Creator Detail Page
async function loadCreatorData(slug) {
    const data = await fetchAPI(`/creator/${slug}`);

    if (!data || !data.creator) {
        document.getElementById('creator-name').textContent = 'Creator Not Found';
        return;
    }

    const { creator, predictions, stats } = data;
    const accuracy = creator.accuracy_score || 0;

    // Update header
    document.getElementById('creator-name').textContent = creator.name;
    document.getElementById('creator-description').textContent =
        creator.description || 'Finance YouTuber';
    document.getElementById('creator-channel-link').href = creator.channel_url || '#';

    // Get rank from leaderboard
    const leaderboardData = await fetchAPI('/leaderboard');
    if (leaderboardData && leaderboardData.leaderboard) {
        const rank = leaderboardData.leaderboard.findIndex(c => c.slug === slug) + 1;
        document.getElementById('creator-rank').textContent = rank > 0 ? `#${rank}` : '—';
    }

    // Update score
    document.getElementById('score-value').textContent = formatPercent(accuracy);

    // Update stats
    document.getElementById('stat-total-predictions').textContent = stats.total_predictions || 0;
    document.getElementById('stat-verified-count').textContent = stats.verified_predictions || 0;
    document.getElementById('stat-video-count').textContent = stats.total_videos || 0;

    // Render predictions
    renderPredictions(predictions);

    // Setup filter controls
    setupFilters(predictions);
}

function renderPredictions(predictions, filter = 'all') {
    const container = document.getElementById('predictions-list');
    if (!container) return;

    let filtered = predictions;

    if (filter === 'verified') {
        filtered = predictions.filter(p => p.overall_score !== null);
    } else if (filter === 'bullish') {
        filtered = predictions.filter(p => p.direction === 'bullish');
    } else if (filter === 'bearish') {
        filtered = predictions.filter(p => p.direction === 'bearish');
    }

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🔍</div>
                <h3>No Predictions Found</h3>
                <p>No predictions match the current filter.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filtered.map((pred, index) => {
        const score = pred.overall_score;
        const hasScore = score !== null && score !== undefined;
        const scoreClass = hasScore ? getAccuracyClass(score) : 'pending';
        const scoreText = hasScore ? formatPercent(score) : 'Pending';

        // Generate video link with timestamp
        let videoLink = pred.video_url || '#';
        if (pred.youtube_id && pred.timestamp) {
            const [mins, secs] = pred.timestamp.split(':').map(Number);
            const totalSecs = (mins || 0) * 60 + (secs || 0);
            videoLink = `https://www.youtube.com/watch?v=${pred.youtube_id}&t=${totalSecs}s`;
        }

        return `
            <div class="prediction-card fade-in" style="animation-delay: ${index * 0.05}s">
                <div class="prediction-header">
                    <div class="prediction-meta">
                        <span class="prediction-asset">${pred.asset || 'Market'}</span>
                        <span class="prediction-direction ${pred.direction || 'neutral'}">
                            ${(pred.direction || 'neutral').charAt(0).toUpperCase() + (pred.direction || 'neutral').slice(1)}
                        </span>
                        ${pred.target ? `<span class="prediction-asset">Target: ${pred.target}</span>` : ''}
                    </div>
                    <span class="prediction-score ${scoreClass}">${scoreText}</span>
                </div>

                <div class="prediction-statement">
                    <blockquote>"${pred.statement}"</blockquote>
                </div>

                ${pred.explanation ? `
                    <div class="prediction-outcome">
                        <div class="prediction-outcome-label">What Actually Happened</div>
                        <div class="prediction-outcome-text">${pred.explanation}</div>
                    </div>
                ` : ''}

                <div class="prediction-footer">
                    <a href="${videoLink}" target="_blank" class="prediction-video-link">
                        📺 Watch at ${pred.timestamp || '0:00'} in video
                    </a>
                    <span class="prediction-date">
                        ${pred.timeframe ? `Expected: ${pred.timeframe}` : ''} 
                        ${pred.publish_date ? `• Made on ${formatDate(pred.publish_date)}` : ''}
                    </span>
                </div>
            </div>
        `;
    }).join('');
}

function setupFilters(predictions) {
    const filterBtns = document.querySelectorAll('.filter-btn');

    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Update active state
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Render filtered predictions
            const filter = btn.dataset.filter;
            renderPredictions(predictions, filter);
        });
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Check which page we're on
    const path = window.location.pathname;

    if (path === '/' || path === '/index.html') {
        loadLeaderboard();
    }
    // Creator page is handled by inline script that calls loadCreatorData
});

// Store current predictions for export
let currentPredictions = [];
let currentCreatorSlug = '';

// Override loadCreatorData to store predictions
const originalLoadCreatorData = loadCreatorData;
loadCreatorData = async function (slug) {
    currentCreatorSlug = slug;
    const data = await fetchAPI(`/creator/${slug}`);

    if (!data || !data.creator) {
        document.getElementById('creator-name').textContent = 'Creator Not Found';
        return;
    }

    const { creator, predictions, stats } = data;
    currentPredictions = predictions; // Store for export
    const accuracy = creator.accuracy_score || 0;

    // Update header
    document.getElementById('creator-name').textContent = creator.name;
    document.title = `${creator.name} - Outcomely`;
    document.getElementById('creator-description').textContent =
        creator.description || 'Finance YouTuber';
    document.getElementById('creator-channel-link').href = creator.channel_url || '#';

    // Get rank from leaderboard
    const leaderboardData = await fetchAPI('/leaderboard');
    if (leaderboardData && leaderboardData.leaderboard) {
        const rank = leaderboardData.leaderboard.findIndex(c => c.slug === slug) + 1;
        document.getElementById('creator-rank').textContent = rank > 0 ? `#${rank}` : '—';
    }

    // Update score
    document.getElementById('score-value').textContent = formatPercent(accuracy);

    // Update stats
    document.getElementById('stat-total-predictions').textContent = stats.total_predictions || 0;
    document.getElementById('stat-verified-count').textContent = stats.verified_predictions || 0;
    document.getElementById('stat-video-count').textContent = stats.total_videos || 0;

    // Render predictions
    renderPredictions(predictions);

    // Setup filter controls
    setupFilters(predictions);
};

// Export predictions to CSV
function exportPredictions() {
    if (!currentPredictions.length) {
        alert('No predictions to export');
        return;
    }

    // CSV headers
    const headers = ['Statement', 'Asset', 'Direction', 'Target', 'Timeframe', 'Confidence', 'Status', 'Accuracy Score', 'Timestamp'];

    // Convert predictions to CSV rows
    const rows = currentPredictions.map(p => [
        `"${(p.statement || '').replace(/"/g, '""')}"`,
        p.asset || '',
        p.direction || '',
        p.target || '',
        p.timeframe || '',
        p.confidence || '',
        p.overall_score !== null ? 'Verified' : 'Pending',
        p.overall_score !== null ? (p.overall_score * 100).toFixed(1) + '%' : '',
        p.timestamp || ''
    ].join(','));

    // Combine headers and rows
    const csv = [headers.join(','), ...rows].join('\n');

    // Create download
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', `${currentCreatorSlug}_predictions.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Search functionality
async function searchPredictions(query) {
    if (!query.trim()) return;

    const data = await fetchAPI(`/search?q=${encodeURIComponent(query)}`);

    if (data && data.results) {
        // Display search results
        console.log(`Found ${data.results.length} results for "${query}"`);
        return data.results;
    }
    return [];
}

// Enhanced empty state with CTA
function showEmptyState(container, message, showCTA = false) {
    container.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">📊</div>
            <h3>${message.title}</h3>
            <p>${message.description}</p>
            ${showCTA ? `
                <a href="/about" class="empty-state-btn">
                    Learn How It Works →
                </a>
            ` : ''}
        </div>
    `;
}
