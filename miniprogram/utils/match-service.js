// utils/match-service.js
const { api, get } = require('./api.js')

async function fetchMatches(status = '', paging = {}, options = {}) {
  const silentOptions = { ...options, suppressToast: true }
  try {
    return await api.getPublicMatchesToday(status, paging, silentOptions)
  } catch (publicErr) {
    console.warn('Public match fetch failed, falling back to authenticated API.', publicErr)
    return await api.getMatchesToday(status, paging, options)
  }
}

async function fetchMatchDetail(matchId) {
  const silentOptions = { suppressToast: true }
  try {
    return await api.getPublicMatchDetail(matchId, silentOptions)
  } catch (publicErr) {
    console.warn('Public match detail fetch failed, falling back to authenticated API.', publicErr)
    return await api.getMatchDetail(matchId)
  }
}

// New pagination-friendly endpoints
async function fetchMatchDetailBasic(matchId) {
  // Fast path: only basic info + top company + pagination meta
  return get(
    `/api/public/matches/${matchId}/pagination`,
    { type: 'basic' },
    { needAuth: false, showLoading: false, suppressToast: true }
  )
}

async function fetchMatchDetailPage(matchId, page = 1, pageSize = 20) {
  // Full data but paginated company analyses
  return get(
    `/api/public/matches/${matchId}/pagination`,
    { type: 'full', page, page_size: pageSize },
    { needAuth: false, showLoading: false, suppressToast: true }
  )
}

async function fetchPoissonPrediction(matchId) {
  const silentOptions = { suppressToast: true }
  try {
    return await api.getPublicMatchPoissonPrediction(matchId, silentOptions)
  } catch (publicErr) {
    console.warn('Public Poisson fetch failed, falling back to authenticated API.', publicErr)
    return await api.getMatchPoissonPrediction(matchId)
  }
}

module.exports = {
  fetchMatches,
  fetchMatchDetail,
  fetchMatchDetailBasic,
  fetchMatchDetailPage,
  fetchPoissonPrediction
}
