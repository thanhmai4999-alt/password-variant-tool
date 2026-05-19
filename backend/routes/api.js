const express = require('express');
const router = express.Router();
const passwordGenerator = require('../services/passwordGenerator');

// ============================================
// INPUT VALIDATION
// ============================================

function validateGenerateRequest(req, res) {
  const { data, rules, depth, mode, maxResults } = req.body;

  if (!Array.isArray(data) || data.length === 0) {
    return res.status(400).json({ error: 'Invalid or empty data array' });
  }

  if (data.length > 10000) {
    return res.status(400).json({ error: 'Too many records (max 10000)' });
  }

  if (!Array.isArray(rules) && mode !== 'custom') {
    return res.status(400).json({ error: 'Rules must be an array' });
  }

  if (typeof depth !== 'number' || depth < 1 || depth > 4) {
    return res.status(400).json({ error: 'Depth must be between 1 and 4' });
  }

  if (!['basic', 'advanced', 'custom'].includes(mode)) {
    return res.status(400).json({ error: 'Invalid mode' });
  }

  const max = parseInt(maxResults) || 100000;
  if (max > parseInt(process.env.MAX_RESULTS || 1000000)) {
    return res.status(400).json({ error: 'Max results exceeds limit' });
  }

  return true;
}

// ============================================
// ROUTES
// ============================================

/**
 * POST /generate
 * Generate password variants using rules
 */
router.post('/generate', async (req, res) => {
  try {
    const validation = validateGenerateRequest(req, res);
    if (validation !== true) return;

    const { data, rules, depth, mode, maxResults } = req.body;
    const max = parseInt(maxResults) || 100000;

    const result = await passwordGenerator.generateVariants(
      data,
      rules,
      depth,
      mode,
      max
    );

    res.json({
      success: true,
      count: result.size,
      ratio: data.length > 0 ? (result.size / data.length).toFixed(2) : 0,
      preview: Array.from(result).slice(0, 1000)
    });
  } catch (error) {
    console.error('Generate error:', error);
    res.status(500).json({ error: 'Failed to generate variants' });
  }
});

/**
 * POST /generate/custom
 * Generate variants from custom patterns
 */
router.post('/generate/custom', async (req, res) => {
  try {
    const { data, suffixes, prefixes, separators, maxResults } = req.body;

    if (!Array.isArray(data) || data.length === 0) {
      return res.status(400).json({ error: 'Invalid data array' });
    }

    const max = parseInt(maxResults) || 100000;

    const result = await passwordGenerator.generateCustom(
      data,
      suffixes || [],
      prefixes || [],
      separators || [],
      max
    );

    res.json({
      success: true,
      count: result.size,
      ratio: data.length > 0 ? (result.size / data.length).toFixed(2) : 0,
      preview: Array.from(result).slice(0, 1000)
    });
  } catch (error) {
    console.error('Custom generate error:', error);
    res.status(500).json({ error: 'Failed to generate custom variants' });
  }
});

/**
 * GET /rules
 * Get all available rules
 */
router.get('/rules', (req, res) => {
  const rules = passwordGenerator.getRulesConfig();
  res.json({ success: true, rules });
});

module.exports = router;
