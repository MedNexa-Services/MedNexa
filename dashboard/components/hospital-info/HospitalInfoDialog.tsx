"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  createHospitalInfo,
  updateHospitalInfo,
  type HospitalInfoOut,
  type HospitalInfoCreate,
  type HospitalInfoUpdate,
} from "@/lib/api";
import { useHospital } from "@/contexts/HospitalContext";
import { toast } from "sonner";
import { Bot, HelpCircle, AlertCircle } from "lucide-react";

interface HospitalInfoDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entry?: HospitalInfoOut | null; // If editing
  defaultCategory?: string; // Pre-select category when adding inline
  existingCategories: string[];
  onSuccess: () => void;
}

export function HospitalInfoDialog({
  open,
  onOpenChange,
  entry,
  defaultCategory,
  existingCategories,
  onSuccess,
}: HospitalInfoDialogProps) {
  const { hospitalId } = useHospital();
  const isEditing = !!entry;

  const [category, setCategory] = React.useState("");
  const [question, setQuestion] = React.useState("");
  const [answer, setAnswer] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (entry) {
      setCategory(entry.category);
      setQuestion(entry.question);
      setAnswer(entry.answer);
    } else {
      setCategory(defaultCategory || "");
      setQuestion("");
      setAnswer("");
    }
    setError(null);
  }, [entry, defaultCategory, open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!category.trim()) {
      setError("Category is required (e.g. Parking, OPD Timings, Emergency)");
      return;
    }
    if (!question.trim()) {
      setError("Question is required");
      return;
    }
    if (!answer.trim()) {
      setError("Answer is required");
      return;
    }

    setIsSubmitting(true);
    try {
      if (isEditing && entry) {
        const payload: HospitalInfoUpdate = {
          category: category.trim(),
          question: question.trim(),
          answer: answer.trim(),
        };

        await updateHospitalInfo(entry.id, payload);
        toast.success("FAQ entry updated");
      } else {
        if (!hospitalId) {
          setError("No active hospital context found.");
          return;
        }

        const payload: HospitalInfoCreate = {
          category: category.trim(),
          question: question.trim(),
          answer: answer.trim(),
        };

        await createHospitalInfo(hospitalId, payload);
        toast.success("New FAQ entry added for AI Receptionist");
      }

      onOpenChange(false);
      onSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save FAQ entry";
      setError(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
            <Bot className="w-5 h-5" />
            <DialogTitle className="text-lg font-bold">
              {isEditing ? "Edit AI Knowledge Entry" : "Add AI Knowledge Entry"}
            </DialogTitle>
          </div>
          <DialogDescription className="text-xs text-muted-foreground">
            {isEditing
              ? "Modify the question or answer. The AI receptionist will immediately update its answers on incoming calls."
              : "Add hospital guidelines, OPD timings, directions, or parking rules that the AI receptionist reads to answer caller queries."}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs animate-in fade-in">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 pt-1">
          {/* Category Input / Selection */}
          <div className="space-y-1.5">
            <Label htmlFor="faq-category" className="text-xs font-semibold">
              Category *
            </Label>
            <Input
              id="faq-category"
              placeholder="e.g. Parking, Emergency, OPD Timings, Billing"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              list="category-options"
              required
              className="h-9 text-xs"
            />
            <datalist id="category-options">
              {existingCategories.map((cat) => (
                <option key={cat} value={cat} />
              ))}
            </datalist>
            <p className="text-[11px] text-muted-foreground">
              Group related FAQs together under common headings.
            </p>
          </div>

          {/* Question Input */}
          <div className="space-y-1.5">
            <Label htmlFor="faq-question" className="text-xs font-semibold">
              Question or Query *
            </Label>
            <Input
              id="faq-question"
              placeholder="e.g. Is parking available?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              required
              className="h-9 text-xs"
            />
            <p className="text-[11px] text-muted-foreground">
              What callers or patients are likely to ask the AI receptionist.
            </p>
          </div>

          {/* Answer Textarea */}
          <div className="space-y-1.5">
            <Label htmlFor="faq-answer" className="text-xs font-semibold">
              Verified Hospital Answer *
            </Label>
            <Textarea
              id="faq-answer"
              placeholder="e.g. Free parking for cars and two-wheelers is available in the basement."
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              rows={4}
              required
              className="text-xs resize-none"
            />
            <p className="text-[11px] text-muted-foreground">
              The exact information the AI will read out in English or Hindi.
            </p>
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
              className="text-xs h-9 cursor-pointer"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={isSubmitting}
              className="text-xs h-9 bg-blue-600 hover:bg-blue-700 text-white font-medium cursor-pointer"
            >
              {isSubmitting
                ? "Saving..."
                : isEditing
                ? "Save Changes"
                : "Add to Knowledge Base"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
