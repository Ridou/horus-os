"use client";

import { Dialog } from "radix-ui";
import { X } from "lucide-react";
import type { ReactNode } from "react";

interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  size?: "sm" | "md" | "lg";
  children: ReactNode;
}

const sizeClass: Record<NonNullable<ModalProps["size"]>, string> = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
};

/** Accessible modal dialog built on Radix Dialog (portal, focus trap, Escape to close). */
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  size = "md",
  children,
}: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-bg-primary/80 backdrop-blur-sm animate-fade-in" />
        <Dialog.Content
          className={[
            "fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)]",
            "-translate-x-1/2 -translate-y-1/2 rounded-lg",
            "border border-border-subtle bg-bg-secondary p-6 shadow-2xl animate-fade-in",
            sizeClass[size],
          ].join(" ")}
        >
          <Dialog.Close
            className="absolute right-4 top-4 text-text-muted transition-colors hover:text-text-primary"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </Dialog.Close>
          <Dialog.Title className="text-base font-bold text-text-primary pr-8">
            {title}
          </Dialog.Title>
          {description && (
            <Dialog.Description className="mt-1 text-sm text-text-secondary">
              {description}
            </Dialog.Description>
          )}
          <div className="mt-4">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default Modal;
