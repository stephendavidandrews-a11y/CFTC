const RULES = {
  matter: {
    title:       { required: true, label: "Title" },
    matter_type: { required: true, label: "Matter Type" },
    outcome_summary: {
      requiredWhen: (data) => data.status === "closed",
      label: "Outcome Summary",
    },
  },
  task: {
    title: { required: true, label: "Title" },
  },
  person: {
    first_name: { required: true, label: "First Name" },
    last_name:  { required: true, label: "Last Name" },
  },
  decision: {
    title:     { required: true, label: "Title" },
    matter_id: { required: true, label: "Matter" },
  },
  organization: {
    name: { required: true, label: "Name" },
  },
  document: {
    title:         { required: true, label: "Title" },
    document_type: { required: true, label: "Document Type" },
  },
  meeting: {
    title:           { required: true, label: "Title" },
    date_time_start: { required: true, label: "Start Time" },
  },
};

/**
 * Validate form data against rules for a resource type.
 * @returns {{ valid: boolean, errors: Record<string, string> }}
 */
export function validate(resourceType, data) {
  const rules = RULES[resourceType];
  if (!rules) return { valid: true, errors: {} };
  const errors = {};
  for (const [field, rule] of Object.entries(rules)) {
    const val = data[field];
    const empty = val === undefined || val === null || val === ""
      || (typeof val === "string" && !val.trim());
    if (rule.required && empty) {
      errors[field] = `${rule.label} is required`;
    }
    if (rule.requiredWhen && rule.requiredWhen(data) && empty) {
      errors[field] = `${rule.label} is required`;
    }
  }
  return { valid: Object.keys(errors).length === 0, errors };
}
