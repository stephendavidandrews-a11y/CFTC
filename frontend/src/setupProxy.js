/**
 * Dev proxy configuration for multiple backends.
 *
 * /tracker/*  -> Tracker service (port 8004)

module.exports = function (app) {
  // Tracker backend
  app.use(
    "/tracker",
    createProxyMiddleware({
      target: "http://localhost:8004",
      changeOrigin: true,
    })
  );

  // Pipeline backend
  // Intake backend (voice pipeline + speaker review)
  app.use(
    "/intake",
    createProxyMiddleware({
      target: "http://localhost:8005",
      changeOrigin: true,
    })
  );
};
