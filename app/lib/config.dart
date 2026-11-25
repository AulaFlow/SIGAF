const apiUrl = String.fromEnvironment(
  'API_URL',
  defaultValue: 'http://localhost:8000',
);
const demo = bool.fromEnvironment('DEMO', defaultValue: false);
