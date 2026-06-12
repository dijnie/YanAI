"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Copy, Download, Gift, LoaderCircle, Plus, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { createRedeemCodes, deleteRedeemCodes, fetchRedeemCodes, updateRedeemCode, type RedeemCode } from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";

function downloadRedeemCodes(codes: RedeemCode[]) {
  const content = `${codes.map((item) => item.code).join("\n")}\n`;
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `redeem-codes-${Date.now()}.txt`;
  link.click();
  URL.revokeObjectURL(url);
}

function RedeemCodesContent() {
  const [items, setItems] = useState<RedeemCode[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<RedeemCode[] | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [form, setForm] = useState({ quota: "10", count: "10", max_uses: "1", expires_at: "", note: "" });
  const selectedCodes = items.filter((item) => selectedIds.includes(item.id));
  const allSelected = items.length > 0 && items.every((item) => selectedIds.includes(item.id));
  const deleteCount = deleteTarget?.length ?? 0;
  const deleteDescription =
    deleteCount === 1
      ? `Delete redeem code "${deleteTarget?.[0]?.code}"? It can no longer be used after deletion.`
      : `Delete the ${deleteCount} selected redeem codes? They can no longer be used after deletion.`;

  const load = async () => {
    setIsLoading(true);
    try {
      const data = await fetchRedeemCodes();
      setItems(data.items);
      setSelectedIds((current) => current.filter((id) => data.items.some((item) => item.id === id)));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load redeem codes");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleCreate = async () => {
    try {
      const data = await createRedeemCodes({
        quota: Number(form.quota || 1),
        count: Number(form.count || 1),
        max_uses: Number(form.max_uses || 1),
        expires_at: form.expires_at || undefined,
        note: form.note,
      });
      setItems(data.items);
      setSelectedIds((current) => current.filter((id) => data.items.some((item) => item.id === id)));
      await navigator.clipboard.writeText(data.created.map((item) => item.code).join("\n"));
      toast.success(`Generated ${data.created.length} redeem codes and copied them to the clipboard`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to generate redeem codes");
    }
  };

  const handleToggle = async (item: RedeemCode) => {
    try {
      const data = await updateRedeemCode(item.id, { status: item.status === "enabled" ? "disabled" : "enabled" });
      setItems(data.items);
      setSelectedIds((current) => current.filter((id) => data.items.some((row) => row.id === id)));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update redeem code");
    }
  };

  const toggleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds((current) => Array.from(new Set([...current, ...items.map((item) => item.id)])));
      return;
    }
    setSelectedIds([]);
  };

  const openDeleteCodes = (codes: RedeemCode[]) => {
    if (codes.length === 0) {
      toast.error("Select the redeem codes to delete first");
      return;
    }
    setDeleteTarget(codes);
  };

  const handleExportCodes = () => {
    if (selectedCodes.length === 0) {
      toast.error("Select the redeem codes to export first");
      return;
    }
    downloadRedeemCodes(selectedCodes);
    toast.success(`Exported ${selectedCodes.length} redeem codes`);
  };

  const handleDeleteCodes = async () => {
    if (!deleteTarget || deleteTarget.length === 0) return;
    setIsDeleting(true);
    try {
      const data = await deleteRedeemCodes(deleteTarget.map((item) => item.id));
      setItems(data.items);
      setSelectedIds((current) => current.filter((id) => data.items.some((item) => item.id === id)));
      setDeleteTarget(null);
      toast.success(`Deleted ${data.removed} redeem codes`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to delete redeem codes");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <section className="space-y-5">
      <div className="flex items-end justify-between gap-4">
        <div className="space-y-1">
          <div className="text-xs font-semibold tracking-[0.18em] text-rose-400 uppercase">Redeem</div>
          <h1 className="text-2xl font-semibold tracking-tight">Redeem Codes</h1>
        </div>
        <Button variant="outline" className="h-10 rounded-xl border-rose-100 bg-white" onClick={() => void load()}>
          <RefreshCw className="size-4" />
          Refresh
        </Button>
      </div>

      <Card className="rounded-lg border-white/80 bg-white/80 shadow-sm">
        <CardContent className="space-y-4 p-5">
          <div className="flex items-center gap-2 text-sm font-semibold text-stone-800">
            <Plus className="size-4 text-rose-500" />
            Batch Generate Redeem Codes
          </div>
          <div className="grid gap-3 md:grid-cols-[120px_120px_120px_180px_1fr_auto]">
            <Input type="number" value={form.quota} onChange={(event) => setForm((current) => ({ ...current, quota: event.target.value }))} placeholder="Quota" className="h-10 rounded-xl border-rose-100 bg-white" />
            <Input type="number" value={form.count} onChange={(event) => setForm((current) => ({ ...current, count: event.target.value }))} placeholder="Count" className="h-10 rounded-xl border-rose-100 bg-white" />
            <Input type="number" value={form.max_uses} onChange={(event) => setForm((current) => ({ ...current, max_uses: event.target.value }))} placeholder="Max uses" className="h-10 rounded-xl border-rose-100 bg-white" />
            <Input value={form.expires_at} onChange={(event) => setForm((current) => ({ ...current, expires_at: event.target.value }))} placeholder="Expiry time (optional)" className="h-10 rounded-xl border-rose-100 bg-white" />
            <Input value={form.note} onChange={(event) => setForm((current) => ({ ...current, note: event.target.value }))} placeholder="Note" className="h-10 rounded-xl border-rose-100 bg-white" />
            <Button className="h-10 rounded-xl bg-rose-500 text-white hover:bg-rose-600" onClick={() => void handleCreate()}>
              Generate
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="overflow-hidden rounded-lg border-white/80 bg-white/80 shadow-sm">
        <CardContent className="p-0">
          <div className="flex flex-wrap items-center gap-3 border-b border-rose-50 px-5 py-3">
            <label className="flex items-center gap-2 text-sm text-stone-500">
              <Checkbox
                checked={allSelected}
                onCheckedChange={(checked) => toggleSelectAll(Boolean(checked))}
                aria-label="Select all redeem codes"
              />
              Select all
            </label>
            <Button
              variant="ghost"
              className="h-8 rounded-lg px-3 text-rose-500 hover:bg-rose-50 hover:text-rose-600"
              onClick={handleExportCodes}
              disabled={selectedCodes.length === 0}
            >
              <Download className="size-4" />
              Export selected
            </Button>
            <Button
              variant="ghost"
              className="h-8 rounded-lg px-3 text-rose-500 hover:bg-rose-50 hover:text-rose-600"
              onClick={() => openDeleteCodes(selectedCodes)}
              disabled={selectedCodes.length === 0 || isDeleting}
            >
              {isDeleting ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              Delete selected
            </Button>
            {selectedCodes.length > 0 ? (
              <span className="rounded-lg bg-stone-100 px-2.5 py-1 text-xs font-medium text-stone-600">
                {selectedCodes.length} selected
              </span>
            ) : null}
          </div>
          {isLoading ? (
            <div className="flex h-40 items-center justify-center">
              <LoaderCircle className="size-5 animate-spin text-rose-400" />
            </div>
          ) : items.length === 0 ? (
            <div className="px-6 py-14 text-center text-sm text-stone-500">No redeem codes yet</div>
          ) : (
            items.map((item) => (
              <div key={item.id} className="grid gap-3 border-b border-rose-50 px-5 py-4 text-sm last:border-0 lg:grid-cols-[44px_1.4fr_100px_100px_120px_160px_180px] lg:items-center">
                <Checkbox
                  checked={selectedIds.includes(item.id)}
                  onCheckedChange={(checked) => {
                    setSelectedIds((current) =>
                      checked
                        ? Array.from(new Set([...current, item.id]))
                        : current.filter((id) => id !== item.id),
                    );
                  }}
                  aria-label={`Select redeem code ${item.code}`}
                />
                <div className="flex min-w-0 items-center gap-3">
                  <div className="rounded-2xl bg-rose-50 p-3 text-rose-500">
                    <Gift className="size-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="truncate font-mono font-semibold text-stone-900">{item.code}</div>
                    <div className="truncate text-xs text-stone-400">{item.note || "No note"}</div>
                  </div>
                </div>
                <div className="font-semibold text-rose-600">{item.quota} pts</div>
                <div className="text-stone-600">{item.used_count}/{item.max_uses}</div>
                <Badge variant={item.status === "enabled" ? "success" : "secondary"}>{item.status === "enabled" ? "Enabled" : "Disabled"}</Badge>
                <div className="text-xs text-stone-500">{item.expires_at || "Never expires"}</div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="h-8 rounded-lg border-rose-100 bg-white" onClick={() => void handleToggle(item)}>
                    {item.status === "enabled" ? "Disable" : "Enable"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-8 text-stone-500"
                    onClick={() => {
                      void navigator.clipboard.writeText(item.code);
                      toast.success("Redeem code copied");
                    }}
                  >
                    <Copy className="size-4" />
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Dialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <div className="mb-1 flex size-10 items-center justify-center rounded-full bg-rose-50 text-rose-500">
              <AlertTriangle className="size-5" />
            </div>
            <DialogTitle>{deleteCount === 1 ? "Delete Redeem Code" : "Delete Redeem Codes"}</DialogTitle>
            <DialogDescription>{deleteDescription}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" className="rounded-xl border-stone-200 bg-white" onClick={() => setDeleteTarget(null)} disabled={isDeleting}>
              Cancel
            </Button>
            <Button variant="destructive" className="rounded-xl" onClick={() => void handleDeleteCodes()} disabled={isDeleting}>
              {isDeleting ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

export default function RedeemCodesPage() {
  const { isCheckingAuth, session } = useAuthGuard(["admin"]);
  if (isCheckingAuth || !session) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoaderCircle className="size-5 animate-spin text-rose-400" />
      </div>
    );
  }
  return <RedeemCodesContent />;
}
