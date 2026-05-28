module.exports = ({ config }) => ({ ...config, web: { ...(config.web || {}), bundler: "metro" } });
