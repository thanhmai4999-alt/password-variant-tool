// ============================================
// PASSWORD GENERATOR SERVICE
// ============================================

const MAX_LENGTH = 20;

const RULES_CONFIG = [
  {
    id: 1,
    name: "📝 Viết thường/hoa/Capitalize",
    rules: [
      { id: "1a", label: "Viết thường (lowercase)" },
      { id: "1b", label: "Viết hoa (UPPERCASE)" },
      { id: "1c", label: "Hoa đầu tiên (Capitalize)" }
    ]
  },
  {
    id: 2,
    name: "🔢 Thêm số phổ biến",
    rules: [
      { id: "2a", label: "+123" },
      { id: "2b", label: "+1234" },
      { id: "2c", label: "+12345" },
      { id: "2d", label: "+123456" },
      { id: "2e", label: "+1234567" },
      { id: "2f", label: "+12345678" },
      { id: "2g", label: "+123456789" }
    ]
  },
  {
    id: 3,
    name: "📅 Thêm năm phổ biến",
    rules: [
      { id: "3a", label: "+1990" },
      { id: "3b", label: "+2000" },
      { id: "3c", label: "+2010" },
      { id: "3d", label: "+2020" },
      { id: "3e", label: "+2024" },
      { id: "3f", label: "+90" },
      { id: "3g", label: "+95" }
    ]
  },
  {
    id: 4,
    name: "🔣 Thêm ký tự đặc biệt",
    rules: [
      { id: "4a", label: "+@" },
      { id: "4b", label: "+@@" },
      { id: "4c", label: "+!" },
      { id: "4d", label: "+!!" },
      { id: "4e", label: "+#" },
      { id: "4f", label: "+$" }
    ]
  },
  {
    id: 5,
    name: "🎯 Hậu tố kiểu Việt",
    rules: [
      { id: "5a", label: "+vip" },
      { id: "5b", label: "+pro" },
      { id: "5c", label: "+cute" },
      { id: "5d", label: "+love" },
      { id: "5e", label: "+baby" },
      { id: "5f", label: "+hihi" },
      { id: "5g", label: "+kaka" }
    ]
  },
  {
    id: 6,
    name: "💠 Chuyển sang LEET speak",
    rules: [
      { id: "6a", label: "a→@" },
      { id: "6b", label: "o→0" },
      { id: "6c", label: "i→1" },
      { id: "6d", label: "e→3" },
      { id: "6e", label: "s→$" },
      { id: "6f", label: "t→7" }
    ]
  },
  {
    id: 7,
    name: "➖ Thêm dấu phân cách",
    rules: [
      { id: "7a", label: "chèn _" },
      { id: "7b", label: "chèn -" },
      { id: "7c", label: "chèn ." }
    ]
  },
  {
    id: 8,
    name: "🔄 Đảo ngược",
    rules: [
      { id: "8a", label: "Reverse toàn bộ" },
      { id: "8b", label: "Reverse chữ, giữ số" }
    ]
  },
  {
    id: 9,
    name: "📦 Nhân đôi & Lặp lại",
    rules: [
      { id: "9a", label: "Double (xxx→xxxxx)" },
      { id: "9b", label: "+Pass 2x" }
    ]
  },
  {
    id: 10,
    name: "👤 Từ Username",
    rules: [
      { id: "10a", label: "User+123" },
      { id: "10b", label: "User+@" },
      { id: "10c", label: "User+1999" },
      { id: "10d", label: "User@123" }
    ]
  },
  {
    id: 11,
    name: "🔗 Ghép & Biến đổi",
    rules: [
      { id: "11a", label: "Thêm số cuối (111→1111)" },
      { id: "11b", label: "Thêm số đầu (111→1111)" },
      { id: "11c", label: "CamelCase (hello→Hello)" }
    ]
  },
  {
    id: 12,
    name: "☎️ Biến đổi số điện thoại",
    rules: [
      { id: "12a", label: "SĐT+@" },
      { id: "12b", label: "SĐT+123" },
      { id: "12c", label: "SĐT+vip" }
    ]
  }
];

const LEET_MAP = {
  a: ["@", "4"],
  o: ["0"],
  s: ["$", "5"],
  e: ["3"],
  i: ["1"],
  t: ["7"]
};

// ============================================
// UTILITY FUNCTIONS
// ============================================

function tokenize(pwd) {
  return pwd.match(/[A-Za-z]+|\d+|[^A-Za-z0-9]/g) || [];
}

function isPhoneNumber(str) {
  return /^0\d{9,10}$/.test(str.replace(/\D/g, ""));
}

function hasEntropyIssue(str) {
  if (/^(.)\1{3,}$/.test(str)) return true;

  for (let len = 1; len <= str.length / 2; len++) {
    const pattern = str.substring(0, len);
    let expected = "";
    for (let i = 0; i < str.length; i += len) {
      expected += pattern;
    }
    if (str === expected.substring(0, str.length) && str.length >= len * 2) {
      return true;
    }
  }

  return false;
}

function validVariant(variant, original) {
  if (!variant) return false;
  if (variant === original) return false;
  if (variant.length > MAX_LENGTH) return false;
  if (hasEntropyIssue(variant)) return false;
  return true;
}

// ============================================
// TRANSFORMATION RULES
// ============================================

const RULES_MAP = {
  "1a": (t) => [t.join("").toLowerCase()],
  "1b": (t) => [t.join("").toUpperCase()],
  "1c": (t) => {
    const str = t.join("");
    for (let i = 0; i < str.length; i++) {
      if (/[a-zA-Z]/.test(str[i])) {
        return [str.substring(0, i) + str[i].toUpperCase() + str.substring(i + 1)];
      }
    }
    return [];
  },
  "2a": (t) => [t.join("") + "123"],
  "2b": (t) => [t.join("") + "1234"],
  "2c": (t) => [t.join("") + "12345"],
  "2d": (t) => [t.join("") + "123456"],
  "2e": (t) => [t.join("") + "1234567"],
  "2f": (t) => [t.join("") + "12345678"],
  "2g": (t) => [t.join("") + "123456789"],
  "3a": (t) => [t.join("") + "1990"],
  "3b": (t) => [t.join("") + "2000"],
  "3c": (t) => [t.join("") + "2010"],
  "3d": (t) => [t.join("") + "2020"],
  "3e": (t) => [t.join("") + "2024"],
  "3f": (t) => [t.join("") + "90"],
  "3g": (t) => [t.join("") + "95"],
  "4a": (t) => [t.join("") + "@"],
  "4b": (t) => [t.join("") + "@@"],
  "4c": (t) => [t.join("") + "!"],
  "4d": (t) => [t.join("") + "!!"],
  "4e": (t) => [t.join("") + "#"],
  "4f": (t) => [t.join("") + "$"],
  "5a": (t) => [t.join("") + "vip"],
  "5b": (t) => [t.join("") + "pro"],
  "5c": (t) => [t.join("") + "cute"],
  "5d": (t) => [t.join("") + "love"],
  "5e": (t) => [t.join("") + "baby"],
  "5f": (t) => [t.join("") + "hihi"],
  "5g": (t) => [t.join("") + "kaka"],
  "6a": (t) => [t.join("").replace(/[aA]/g, "@")],
  "6b": (t) => [t.join("").replace(/[oO]/g, "0")],
  "6c": (t) => [t.join("").replace(/[iI]/g, "1")],
  "6d": (t) => [t.join("").replace(/[eE]/g, "3")],
  "6e": (t) => [t.join("").replace(/[sS]/g, "$")],
  "6f": (t) => [t.join("").replace(/[tT]/g, "7")],
  "7a": (t) => {
    const w = t.join("");
    const m = w.match(/^([A-Za-z]+)(\d+)$/) || w.match(/^(\d+)([A-Za-z]+)$/);
    if (m) {
      const letters = /[a-zA-Z]/.test(m[1]) ? m[1] : m[2];
      const digits = /\d/.test(m[1]) ? m[1] : m[2];
      return [letters + "_" + digits];
    }
    return [];
  },
  "7b": (t) => {
    const w = t.join("");
    const m = w.match(/^([A-Za-z]+)(\d+)$/) || w.match(/^(\d+)([A-Za-z]+)$/);
    if (m) {
      const letters = /[a-zA-Z]/.test(m[1]) ? m[1] : m[2];
      const digits = /\d/.test(m[1]) ? m[1] : m[2];
      return [letters + "-" + digits];
    }
    return [];
  },
  "7c": (t) => {
    const w = t.join("");
    const m = w.match(/^([A-Za-z]+)(\d+)$/) || w.match(/^(\d+)([A-Za-z]+)$/);
    if (m) {
      const letters = /[a-zA-Z]/.test(m[1]) ? m[1] : m[2];
      const digits = /\d/.test(m[1]) ? m[1] : m[2];
      return [letters + "." + digits];
    }
    return [];
  },
  "8a": (t) => [t.join("").split("").reverse().join("")],
  "8b": (t) => {
    const w = t.join("");
    const letters = (w.match(/[A-Za-z]/g) || []);
    const nonLetters = (w.match(/[^A-Za-z]/g) || []);
    return [letters.reverse().join("") + nonLetters.join("")];
  },
  "9a": (t) => {
    const w = t.join("");
    if ((w.length * 2) > MAX_LENGTH) return [];
    return [w + w];
  },
  "9b": (t) => {
    const w = t.join("");
    if ((w.length * 2) > MAX_LENGTH) return [];
    return [w + w];
  },
  "10a": (user) => {
    const base = user.split("@")[0];
    return base ? [base + "123"] : [];
  },
  "10b": (user) => {
    const base = user.split("@")[0];
    return base ? [base + "@"] : [];
  },
  "10c": (user) => {
    const base = user.split("@")[0];
    return base ? [base + "1999"] : [];
  },
  "10d": (user) => {
    const base = user.split("@")[0];
    return base ? [base + "@123"] : [];
  },
  "11a": (t) => {
    const w = t.join("");
    const lastNum = w.match(/\d+$/);
    if (lastNum) {
      const num = lastNum[0];
      const rest = w.substring(0, w.length - num.length);
      return [rest + num + num.charAt(0)];
    }
    return [];
  },
  "11b": (t) => {
    const w = t.join("");
    const firstNum = w.match(/^\d+/);
    if (firstNum) {
      const num = firstNum[0];
      return [num + num.charAt(0) + w.substring(num.length)];
    }
    return [];
  },
  "11c": (t) => {
    const w = t.join("");
    return [w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()];
  },
  "12a": (t) => {
    const w = t.join("");
    if (isPhoneNumber(w)) {
      return [w + "@"];
    }
    return [];
  },
  "12b": (t) => {
    const w = t.join("");
    if (isPhoneNumber(w)) {
      return [w + "123"];
    }
    return [];
  },
  "12c": (t) => {
    const w = t.join("");
    if (isPhoneNumber(w)) {
      return [w + "vip"];
    }
    return [];
  }
};

// ============================================
// MAIN FUNCTIONS
// ============================================

async function generateVariants(data, rules, depth, mode, maxResults) {
  const results = new Set();
  const chunkSize = parseInt(process.env.CHUNK_SIZE || 500);

  for (let i = 0; i < data.length; i += chunkSize) {
    if (results.size >= maxResults) break;

    const chunk = data.slice(i, i + chunkSize);

    for (const item of chunk) {
      if (results.size >= maxResults) break;

      const origPass = item.pass;
      const user = item.user;

      if (mode === "basic") {
        const tokens = tokenize(origPass);
        for (const ruleId of rules) {
          if (results.size >= maxResults) break;

          const ruleFn = RULES_MAP[ruleId];
          if (!ruleFn) continue;

          try {
            const variants = ruleId.startsWith("10") || ruleId.startsWith("12")
              ? ruleFn(user)
              : ruleFn(tokens);
            const variantsArray = Array.isArray(variants) ? variants : [variants];

            for (const v of variantsArray) {
              if (results.size >= maxResults) break;
              if (validVariant(v, origPass)) {
                results.add(`${user.toLowerCase()}:${v}`);
              }
            }
          } catch (e) {
            console.error(`Error in rule ${ruleId}:`, e.message);
          }
        }
      } else if (mode === "advanced") {
        const variants = await applyRuleChain(origPass, user, rules, depth, maxResults - results.size);
        for (const v of variants) {
          if (results.size >= maxResults) break;
          results.add(`${user.toLowerCase()}:${v}`);
        }
      }
    }
  }

  return results;
}

async function applyRuleChain(base, user, selectedRules, depth, limit) {
  const results = new Set([base]);
  let currentLayer = [base];

  for (let layer = 0; layer < depth; layer++) {
    const nextLayer = new Set();

    for (const pwd of currentLayer) {
      const tokens = tokenize(pwd);

      for (const ruleId of selectedRules) {
        if (results.size >= limit) break;

        const ruleFn = RULES_MAP[ruleId];
        if (!ruleFn) continue;

        try {
          const variants = ruleId.startsWith("10") ? ruleFn(user) : ruleFn(tokens);
          const variantsArray = Array.isArray(variants) ? variants : [variants];

          for (const v of variantsArray) {
            if (results.size >= limit) break;
            if (validVariant(v, base)) {
              results.add(v);
              nextLayer.add(v);
            }
          }
        } catch (e) {
          console.error(`Error in rule ${ruleId}:`, e.message);
        }
      }
    }

    currentLayer = Array.from(nextLayer);
    if (currentLayer.length === 0) break;
  }

  results.delete(base);
  return Array.from(results);
}

async function generateCustom(data, suffixes, prefixes, separators, maxResults) {
  const results = new Set();

  for (const item of data) {
    if (results.size >= maxResults) break;

    const pass = item.pass;
    const user = item.user;

    // Add suffixes
    for (const suffix of suffixes) {
      const variant = pass + suffix;
      if (validVariant(variant, pass) && variant.length <= MAX_LENGTH) {
        results.add(`${user.toLowerCase()}:${variant}`);
      }
    }

    // Add prefixes
    for (const prefix of prefixes) {
      const variant = prefix + pass;
      if (validVariant(variant, pass) && variant.length <= MAX_LENGTH) {
        results.add(`${user.toLowerCase()}:${variant}`);
      }
    }

    // Add separators
    for (const sep of separators) {
      const m = pass.match(/^([A-Za-z]+)(\d+)$/) || pass.match(/^(\d+)([A-Za-z]+)$/);
      if (m) {
        const letters = /[a-zA-Z]/.test(m[1]) ? m[1] : m[2];
        const digits = /\d/.test(m[1]) ? m[1] : m[2];
        const variant = letters + sep + digits;
        if (validVariant(variant, pass) && variant.length <= MAX_LENGTH) {
          results.add(`${user.toLowerCase()}:${variant}`);
        }
      }
    }
  }

  return results;
}

function getRulesConfig() {
  return RULES_CONFIG;
}

module.exports = {
  generateVariants,
  generateCustom,
  getRulesConfig
};
