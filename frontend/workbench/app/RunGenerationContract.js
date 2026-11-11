const text = value => typeof value === 'string';
const labels = { min_overdue: '交期优先', min_tardiness: '拖期更轻', min_changeover: '切换更少', min_weighted_tardiness: '加权拖期更轻' };
const budget = value => Number.isInteger(value) && value >= 1;
const objective = value => text(value) && Object.prototype.hasOwnProperty.call(labels, value);
const objectiveLabel = value => labels[value] || value;
const RunGenerationContract = { budget, objective, objectiveLabel };
export { RunGenerationContract, budget, objective, objectiveLabel };
export default RunGenerationContract;
