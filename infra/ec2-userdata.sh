#!/bin/bash
set -euxo pipefail
dnf install -y nginx
cat > /usr/share/nginx/html/index.html <<'EOF'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CSE363 Learning Platform</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      font-family: Arial, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
    }
    main {
      width: min(680px, 85%);
      padding: 48px;
      border: 1px solid #334155;
      border-radius: 18px;
      background: #1e293b;
      box-shadow: 0 20px 60px rgba(0,0,0,.3);
    }
    h1 { margin-top: 0; color: #38bdf8; }
    .status { color: #4ade80; font-weight: bold; }
  </style>
</head>
<body>
  <main>
    <h1>CSE363 Cloud Learning Platform</h1>
    <p class="status">Infrastructure Layer Online</p>
    <p>The Application Load Balancer successfully reached the application instance.</p>
    <p>Milestone 1 placeholder page.</p>
  </main>
</body>
</html>
EOF
printf 'OK\n' > /usr/share/nginx/html/health
systemctl enable nginx
systemctl start nginx
