import express from "express";
import cors from "cors";
import morgan from "morgan";
import mongoose from "mongoose";

const PORT = process.env.PORT || 3000;
const MONGODB_URI = process.env.MONGODB_URI || "mongodb://localhost:27017/incidents";

const IncidentSchema = new mongoose.Schema(
  {
    correlation_id: { type: String, required: true, index: true },
    timestamp: { type: Date, required: true, index: true },
    service_name: { type: String, required: true, index: true },
    severity: { type: String, required: true },
    error_rate_percent: { type: Number, required: true },
    latency_ms: { type: Number, required: true },
    db_pool_utilization: { type: Number, required: true },
    probable_root_cause: { type: String, required: true },
    recommended_actions: { type: String, required: true },
    raw: { type: Object, required: false }
  },
  { minimize: false }
);

IncidentSchema.index({ service_name: 1, timestamp: -1 });

const Incident = mongoose.model("Incident", IncidentSchema);

const app = express();
app.use(cors());
app.use(express.json({ limit: "1mb" }));
app.use(morgan("combined"));

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.post("/incident-report", async (req, res) => {
  const body = req.body || {};
  const required = [
    "correlation_id",
    "timestamp",
    "service_name",
    "severity",
    "error_rate_percent",
    "latency_ms",
    "db_pool_utilization",
    "probable_root_cause",
    "recommended_actions"
  ];

  for (const key of required) {
    if (body[key] === undefined || body[key] === null || body[key] === "") {
      return res.status(400).json({ error: `Missing required field: ${key}` });
    }
  }

  const incident = await Incident.create({
    correlation_id: String(body.correlation_id),
    timestamp: new Date(body.timestamp),
    service_name: String(body.service_name),
    severity: String(body.severity),
    error_rate_percent: Number(body.error_rate_percent),
    latency_ms: Number(body.latency_ms),
    db_pool_utilization: Number(body.db_pool_utilization),
    probable_root_cause: String(body.probable_root_cause),
    recommended_actions: String(body.recommended_actions),
    raw: body
  });

  res.status(201).json({ id: incident._id, correlation_id: incident.correlation_id });
});

app.get("/incidents", async (_req, res) => {
  const incidents = await Incident.find({}).sort({ timestamp: -1 }).limit(200).lean();
  res.json(incidents);
});

app.get("/incidents/:id", async (req, res) => {
  const incident = await Incident.findById(req.params.id).lean();
  if (!incident) return res.status(404).json({ error: "Not found" });
  res.json(incident);
});

async function start() {
  await mongoose.connect(MONGODB_URI);
  app.listen(PORT, () => {
    console.log(`incident-api listening on :${PORT}`);
  });
}

start().catch((err) => {
  console.error("Failed to start incident-api", err);
  process.exit(1);
});
