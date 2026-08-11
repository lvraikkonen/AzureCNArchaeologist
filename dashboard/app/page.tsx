import Dashboard from "./Dashboard";
import projectionJson from "./generated/capability-dashboard.json";
import { assertDashboardProjection } from "./dashboard-model";

const projection: unknown = projectionJson;
assertDashboardProjection(projection);
const checkedProjection = projection;

export default function Home() {
  return <Dashboard projection={checkedProjection} />;
}
