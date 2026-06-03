"use client";

import { useState } from "react";
import { Plug } from "lucide-react";
import { useIntegrations } from "@/lib/hooks";
import { isDemoMode } from "@/lib/api";
import { PageHeader, PageSkeleton, EmptyState } from "@/components";
import { ReadinessSummary } from "./ReadinessSummary";
import { IntegrationCard } from "./IntegrationCard";
import { IntegrationWalkthrough } from "./IntegrationWalkthrough";
import type { IntegrationStatus } from "@/lib/types";

export default function IntegrationsPage() {
  const { data, isLoading } = useIntegrations();
  const [selected, setSelected] = useState<IntegrationStatus | null>(null);
  const [currentStep, setCurrentStep] = useState(0);

  function openWalkthrough(integration: IntegrationStatus) {
    setSelected(integration);
    setCurrentStep(0);
  }

  function closeWalkthrough() {
    setSelected(null);
  }

  return (
    <div>
      <PageHeader
        title="Integrations"
        description="Connect external services and tools to extend your agents."
      />
      {isLoading ? (
        <PageSkeleton variant="list" />
      ) : !data ? (
        <EmptyState
          icon={Plug}
          heading="No integrations data"
          message="Could not load integration status. Check that horus-os is running."
        />
      ) : (
        <>
          <ReadinessSummary integrations={data.integrations} />
          <div data-tour-step="9" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.integrations.map((integration) => (
              <IntegrationCard
                key={integration.id}
                integration={integration}
                onViewWalkthrough={() => openWalkthrough(integration)}
              />
            ))}
          </div>
        </>
      )}
      {selected && (
        <IntegrationWalkthrough
          integration={selected}
          open={!!selected}
          onClose={closeWalkthrough}
          currentStep={currentStep}
          onStepChange={setCurrentStep}
          demoMode={isDemoMode || (data?.demo_mode ?? false)}
        />
      )}
    </div>
  );
}
