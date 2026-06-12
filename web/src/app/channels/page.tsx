"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, LoaderCircle, Pencil, Plus, RefreshCw, TestTube, Trash2, XCircle } from "lucide-react";
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
import { Textarea } from "@/components/ui/textarea";
import {
  createChannel,
  deleteChannel,
  fetchChannels,
  testChannelModels,
  updateChannel,
  type Channel,
  type ChannelModelTestResult,
} from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";

const DEFAULT_CHANNEL_MODELS =
  "gpt-5,gpt-5-1,gpt-5-2,gpt-5-3,gpt-5-3-mini,gpt-5-5,gpt-5-mini,gpt-image-2,codex-gpt-image-2,auto";

type ChannelForm = {
  name: string;
  base_url: string;
  api_key: string;
  models: string;
  weight: string;
  priority: string;
  timeout: string;
  enabled: boolean;
};

type TextFieldKey = Exclude<keyof ChannelForm, "enabled">;

const EMPTY_FORM: ChannelForm = {
  name: "",
  base_url: "",
  api_key: "",
  models: DEFAULT_CHANNEL_MODELS,
  weight: "1",
  priority: "0",
  timeout: "60",
  enabled: true,
};

const CHANNEL_FIELDS: Array<{
  key: TextFieldKey;
  label: string;
  description: string;
  placeholder: string;
  type?: "number" | "password" | "text";
}> = [
  {
    key: "name",
    label: "Name",
    description: "Channel name shown in lists and logs.",
    placeholder: "Name",
  },
  {
    key: "base_url",
    label: "Base URL",
    description: "OpenAI-compatible service root URL.",
    placeholder: "https://api.example.com",
  },
  {
    key: "api_key",
    label: "API Key",
    description: "Required when creating; leave blank while editing to keep the current secret.",
    placeholder: "sk-...",
    type: "password",
  },
  {
    key: "models",
    label: "Model",
    description: "Comma-separated. This channel is used only when the model matches.",
    placeholder: "gpt-image-2,codex-gpt-image-2",
  },
  {
    key: "weight",
    label: "Weight",
    description: "Random selection weight among channels with the same priority.",
    placeholder: "1",
    type: "number",
  },
  {
    key: "priority",
    label: "Priority",
    description: "Higher values are tried first.",
    placeholder: "0",
    type: "number",
  },
  {
    key: "timeout",
    label: "Timeout",
    description: "Request timeout in seconds.",
    placeholder: "60",
    type: "number",
  },
];

const PRIMARY_FIELDS = CHANNEL_FIELDS.slice(0, 3);
const MODEL_FIELD = CHANNEL_FIELDS.find((field) => field.key === "models") ?? CHANNEL_FIELDS[3];
const ROUTING_FIELDS = CHANNEL_FIELDS.slice(4);

const resetForm = (): ChannelForm => ({ ...EMPTY_FORM });

const channelToForm = (channel: Channel): ChannelForm => ({
  name: channel.name || "",
  base_url: channel.base_url || "",
  api_key: "",
  models: channel.models?.join(",") || "",
  weight: String(channel.weight ?? 1),
  priority: String(channel.priority ?? 0),
  timeout: String(channel.timeout ?? 60),
  enabled: channel.enabled,
});

const toNumber = (value: string, fallback: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const channelTypeLabel = (channel: Channel) =>
  channel.type === "internal_pool" ? "Built-in Account Pool" : "OpenAI Image Compatible";

const uniqueModels = (models: string[] | undefined) => {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const item of models || []) {
    const model = item.trim();
    if (model && !seen.has(model)) {
      seen.add(model);
      result.push(model);
    }
  }
  return result;
};

function FieldCaption({ field }: { field: (typeof CHANNEL_FIELDS)[number] }) {
  return (
    <label className="block text-xs" title={field.description}>
      <span className="block font-semibold text-stone-700">{field.label}</span>
    </label>
  );
}

function FieldHelpStrip() {
  return (
    <div className="grid gap-x-4 gap-y-2 rounded-lg bg-rose-50/55 px-4 py-3 text-xs leading-5 text-stone-500 sm:grid-cols-2 xl:grid-cols-4">
      {CHANNEL_FIELDS.map((field) => (
        <div key={field.key} className="min-w-0">
          <span className="font-semibold text-stone-700">{field.label}</span>
          <span className="mx-1 text-rose-300">/</span>
          <span>{field.description}</span>
        </div>
      ))}
    </div>
  );
}

function ChannelsContent() {
  const [items, setItems] = useState<Channel[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [savingChannelId, setSavingChannelId] = useState<string | null>(null);
  const [testingChannelId, setTestingChannelId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, ChannelModelTestResult>>({});
  const [form, setForm] = useState<ChannelForm>(resetForm);
  const [editingChannel, setEditingChannel] = useState<Channel | null>(null);
  const [editForm, setEditForm] = useState<ChannelForm>(resetForm);
  const [modelTestChannel, setModelTestChannel] = useState<Channel | null>(null);
  const [selectedTestModels, setSelectedTestModels] = useState<string[]>([]);

  const load = async () => {
    setIsLoading(true);
    try {
      const data = await fetchChannels();
      setItems(data.items);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load channels");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;

    fetchChannels()
      .then((data) => {
        if (isMounted) {
          setItems(data.items);
        }
      })
      .catch((error: unknown) => {
        if (isMounted) {
          toast.error(error instanceof Error ? error.message : "Failed to load channels");
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const updateCreateField = (key: TextFieldKey, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const updateEditField = (key: TextFieldKey, value: string) => {
    setEditForm((current) => ({ ...current, [key]: value }));
  };

  const handleCreate = async () => {
    setIsCreating(true);
    try {
      const data = await createChannel({
        name: form.name.trim(),
        base_url: form.base_url.trim(),
        api_key: form.api_key.trim(),
        models: form.models,
        weight: toNumber(form.weight, 1),
        priority: toNumber(form.priority, 0),
        timeout: toNumber(form.timeout, 60),
        enabled: form.enabled,
      });
      setItems(data.items);
      setForm(resetForm());
      toast.success("Channel created");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "CreateChannelFailed");
    } finally {
      setIsCreating(false);
    }
  };

  const handleToggle = async (channel: Channel) => {
    setSavingChannelId(channel.id);
    try {
      const data = await updateChannel(channel.id, { enabled: !channel.enabled });
      setItems(data.items);
      toast.success(channel.enabled ? "Channel disabled" : "Channel enabled");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update channel");
    } finally {
      setSavingChannelId(null);
    }
  };

  const handleDelete = async (channel: Channel) => {
    setSavingChannelId(channel.id);
    try {
      const data = await deleteChannel(channel.id);
      setItems(data.items);
      toast.success("Channel deleted");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "DeleteChannelFailed");
    } finally {
      setSavingChannelId(null);
    }
  };

  const openModelTestDialog = (channel: Channel) => {
    const models = uniqueModels(channel.models);
    setModelTestChannel(channel);
    setSelectedTestModels(models);
  };

  const toggleTestModel = (model: string, checked: boolean) => {
    setSelectedTestModels((current) => {
      if (checked) {
        return current.includes(model) ? current : [...current, model];
      }
      return current.filter((item) => item !== model);
    });
  };

  const handleTestModels = async () => {
    const channel = modelTestChannel;
    if (!channel) return;
    if (selectedTestModels.length <= 0) {
      toast.error("Select at least one model to test");
      return;
    }
    setTestingChannelId(channel.id);
    try {
      const result = await testChannelModels(channel.id, selectedTestModels);
      setTestResults((current) => ({ ...current, [channel.id]: result }));
      if (result.ok) {
        toast.success(`${channel.name} model test passed: ${result.tested_models.length} models, ${result.latency_ms}ms`);
        setModelTestChannel(null);
      } else {
        toast.error(result.error || `${channel.name} ModelTestFailed`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "ModelTestFailed");
    } finally {
      setTestingChannelId(null);
    }
  };

  const openEditDialog = (channel: Channel) => {
    setEditingChannel(channel);
    setEditForm(channelToForm(channel));
  };

  const handleSaveEdit = async () => {
    if (!editingChannel) return;
    setSavingChannelId(editingChannel.id);
    try {
      const isInternal = editingChannel.id === "internal_pool";
      const payload = isInternal
        ? { enabled: editForm.enabled }
        : {
            name: editForm.name.trim(),
            base_url: editForm.base_url.trim(),
            ...(editForm.api_key.trim() ? { api_key: editForm.api_key.trim() } : {}),
            models: editForm.models,
            weight: toNumber(editForm.weight, 1),
            priority: toNumber(editForm.priority, 0),
            timeout: toNumber(editForm.timeout, 60),
            enabled: editForm.enabled,
          };
      const data = await updateChannel(editingChannel.id, payload);
      setItems(data.items);
      setEditingChannel(null);
      toast.success("Channel configuration saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "SaveChannelFailed");
    } finally {
      setSavingChannelId(null);
    }
  };

  const isEditingInternal = editingChannel?.id === "internal_pool";
  const candidateTestModels = uniqueModels(modelTestChannel?.models);
  const selectedTestModelSet = new Set(selectedTestModels);

  return (
    <section className="space-y-5">
      <div className="flex items-end justify-between gap-4">
        <div className="space-y-1">
          <div className="text-xs font-semibold tracking-[0.18em] text-rose-400 uppercase">Channels</div>
          <h1 className="text-2xl font-semibold tracking-tight">Channel Management</h1>
        </div>
        <Button variant="outline" className="h-10 rounded-xl border-rose-100 bg-white" onClick={() => void load()}>
          <RefreshCw className="size-4" />
          Refresh
        </Button>
      </div>

      <Card className="rounded-lg border-white/80 bg-white/80 shadow-sm">
        <CardContent className="space-y-4 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-stone-800">
              <Plus className="size-4 text-rose-500" />
              Added OpenAI Image CompatibleChannel
            </div>
            <div className="text-xs text-stone-400">After entering an OpenAI-compatible URL, you can test the model endpoint from the list.</div>
          </div>
          <div className="grid gap-3 lg:grid-cols-[1fr_1.4fr_1.15fr]">
            {PRIMARY_FIELDS.map((field) => (
              <div key={field.key} className="space-y-1.5">
                <FieldCaption field={field} />
                <Input
                  type={field.type || "text"}
                  value={form[field.key]}
                  onChange={(event) => updateCreateField(field.key, event.target.value)}
                  placeholder={field.placeholder}
                  autoComplete={field.key === "api_key" ? "new-password" : undefined}
                  className="h-10 rounded-xl border-rose-100 bg-white"
                />
              </div>
            ))}
          </div>
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_92px_92px_92px_auto]">
            <div className="space-y-1.5">
              <FieldCaption field={MODEL_FIELD} />
              <Input
                value={form.models}
                onChange={(event) => updateCreateField("models", event.target.value)}
                placeholder={MODEL_FIELD.placeholder}
                className="h-10 rounded-xl border-rose-100 bg-white"
              />
            </div>
            {ROUTING_FIELDS.map((field) => (
              <div key={field.key} className="space-y-1.5">
                <FieldCaption field={field} />
                <Input
                  type={field.type || "text"}
                  value={form[field.key]}
                  onChange={(event) => updateCreateField(field.key, event.target.value)}
                  placeholder={field.placeholder}
                  className="h-10 rounded-xl border-rose-100 bg-white"
                />
              </div>
            ))}
            <Button
              className="h-10 self-end rounded-xl bg-rose-500 text-white hover:bg-rose-600"
              disabled={isCreating}
              onClick={() => void handleCreate()}
            >
              {isCreating ? <LoaderCircle className="size-4 animate-spin" /> : null}
              Create
            </Button>
          </div>
          <FieldHelpStrip />
        </CardContent>
      </Card>

      <Card className="overflow-hidden rounded-lg border-white/80 bg-white/80 shadow-sm">
        <CardContent className="p-0">
          <div className="hidden border-b border-rose-50 px-5 py-3 text-xs font-semibold text-stone-500 lg:grid lg:grid-cols-[1.05fr_1.4fr_1.6fr_1fr_90px_230px] lg:items-center">
            <div>Name / Type</div>
            <div>Base URL</div>
            <div>Model</div>
            <div>Routing</div>
            <div>Status</div>
            <div>Actions</div>
          </div>
          {isLoading ? (
            <div className="flex h-40 items-center justify-center">
              <LoaderCircle className="size-5 animate-spin text-rose-400" />
            </div>
          ) : (
            items.map((channel) => {
              const testResult = testResults[channel.id];
              return (
                <div
                  key={channel.id}
                  className="grid gap-3 border-b border-rose-50 px-5 py-4 text-sm last:border-0 lg:grid-cols-[1.05fr_1.4fr_1.6fr_1fr_90px_230px] lg:items-center"
                >
                  <div>
                    <div className="font-medium text-stone-900">{channel.name}</div>
                    <div className="text-xs text-stone-400">{channelTypeLabel(channel)}</div>
                  </div>
                  <div className="truncate text-stone-600" title={channel.base_url || "Built-in Account Pool"}>
                    {channel.base_url || "Built-in Account Pool"}
                  </div>
                  <div className="truncate text-stone-500" title={channel.models?.join(", ")}>
                    {channel.models?.join(", ")}
                  </div>
                  <div className="flex flex-wrap gap-1.5 text-xs text-stone-500">
                    <Badge variant="outline">Weight {channel.weight}</Badge>
                    <Badge variant="outline">Priority {channel.priority}</Badge>
                    <Badge variant="outline">{channel.timeout ? `${channel.timeout}s` : "No timeout"}</Badge>
                  </div>
                  <Badge variant={channel.enabled ? "success" : "secondary"} className="w-fit">
                    {channel.enabled ? "Enable" : "Disable"}
                  </Badge>
                  <div className="min-w-0 space-y-2">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="icon"
                        className="size-8 rounded-lg border-rose-100 bg-white"
                        title="Edit"
                        aria-label="EditChannel"
                        onClick={() => openEditDialog(channel)}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 rounded-lg border-rose-100 bg-white"
                        disabled={testingChannelId === channel.id}
                        onClick={() => openModelTestDialog(channel)}
                      >
                        {testingChannelId === channel.id ? <LoaderCircle className="size-4 animate-spin" /> : <TestTube className="size-4" />}
                        Test
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 rounded-lg border-rose-100 bg-white"
                        disabled={savingChannelId === channel.id}
                        onClick={() => void handleToggle(channel)}
                      >
                        {savingChannelId === channel.id ? <LoaderCircle className="size-4 animate-spin" /> : null}
                        {channel.enabled ? "Disable" : "Enable"}
                      </Button>
                      {channel.id !== "internal_pool" ? (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-8 text-rose-500"
                          title="Delete"
                          aria-label="DeleteChannel"
                          disabled={savingChannelId === channel.id}
                          onClick={() => void handleDelete(channel)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      ) : null}
                    </div>
                    {testResult ? (
                      <div
                        className={
                          testResult.ok
                            ? "flex min-w-0 items-center gap-1.5 text-xs text-emerald-700"
                            : "flex min-w-0 items-center gap-1.5 text-xs text-rose-600"
                        }
                        title={testResult.ok ? testResult.tested_models.join(", ") : testResult.missing_models.join(", ") || testResult.error}
                      >
                        {testResult.ok ? <CheckCircle2 className="size-3.5 shrink-0" /> : <XCircle className="size-3.5 shrink-0" />}
                        <span className="truncate">
                          {testResult.ok
                            ? `${testResult.tested_models.length} selected models available - ${testResult.latency_ms}ms`
                            : testResult.missing_models.length > 0
                              ? `Missing ${testResult.missing_models.join(", ")}`
                              : testResult.error || "ModelTestFailed"}
                        </span>
                      </div>
                    ) : null}
                  </div>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      <Dialog open={Boolean(modelTestChannel)} onOpenChange={(open) => (!open ? setModelTestChannel(null) : null)}>
        <DialogContent showCloseButton={false} className="flex max-h-[86vh] w-[min(94vw,680px)] max-w-none flex-col overflow-hidden rounded-lg p-0">
          <DialogHeader className="border-b border-rose-100 px-5 pt-5 pb-4 sm:px-6">
            <DialogTitle>Select Test Models</DialogTitle>
            <DialogDescription className="leading-6 text-stone-500">
              {modelTestChannel ? `${modelTestChannel.name} - ${channelTypeLabel(modelTestChannel)}` : "Select models to test"}
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-5 sm:px-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm font-medium text-stone-800">Selected {selectedTestModels.length} / {candidateTestModels.length}</div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 rounded-lg border-rose-100 bg-white"
                  onClick={() => setSelectedTestModels(candidateTestModels)}
                >
                  Select All
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 rounded-lg border-rose-100 bg-white"
                  onClick={() => setSelectedTestModels([])}
                >
                  Clear
                </Button>
              </div>
            </div>

            {candidateTestModels.length > 0 ? (
              <div className="grid max-h-[46vh] gap-2 overflow-y-auto rounded-lg border border-rose-100 bg-white/70 p-3 sm:grid-cols-2">
                {candidateTestModels.map((model) => (
                  <label key={model} className="flex min-w-0 items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-rose-50/80">
                    <Checkbox
                      checked={selectedTestModelSet.has(model)}
                      onCheckedChange={(checked) => toggleTestModel(model, checked === true)}
                    />
                    <span className="truncate text-stone-700" title={model}>{model}</span>
                  </label>
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-rose-100 bg-white/70 p-4 text-sm text-stone-500">
                This channel has no selectable models configured yet.
              </div>
            )}
          </div>

          <DialogFooter className="border-t border-rose-100 px-5 py-4 sm:px-6">
            <Button variant="outline" className="h-10 rounded-xl border-rose-100 bg-white" onClick={() => setModelTestChannel(null)}>
              Cancel
            </Button>
            <Button
              className="h-10 rounded-xl bg-rose-500 text-white hover:bg-rose-600"
              disabled={!modelTestChannel || selectedTestModels.length <= 0 || testingChannelId === modelTestChannel.id}
              onClick={() => void handleTestModels()}
            >
              {modelTestChannel && testingChannelId === modelTestChannel.id ? <LoaderCircle className="size-4 animate-spin" /> : <TestTube className="size-4" />}
              Start Test
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(editingChannel)} onOpenChange={(open) => (!open ? setEditingChannel(null) : null)}>
        <DialogContent showCloseButton={false} className="flex max-h-[88vh] w-[min(94vw,760px)] max-w-none flex-col overflow-hidden rounded-lg p-0">
          <DialogHeader className="border-b border-rose-100 px-5 pt-5 pb-4 sm:px-6">
            <DialogTitle>{isEditingInternal ? "Configure Built-in Account Pool" : "Edit Channel Configuration"}</DialogTitle>
            <DialogDescription className="leading-6 text-stone-500">
              {isEditingInternal ? "The built-in account pool only controls whether fallback to local accounts is allowed." : "Change the channel name, URL, model scope, and routing parameters."}
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5 sm:px-6">
            <label className="flex items-center gap-3 rounded-lg border border-rose-100 bg-white/70 px-4 py-3 text-sm">
              <Checkbox
                checked={editForm.enabled}
                onCheckedChange={(checked) => setEditForm((current) => ({ ...current, enabled: checked === true }))}
              />
              <span className="font-medium text-stone-800">Enable this channel</span>
            </label>

            {isEditingInternal ? (
              <div className="space-y-2 rounded-lg border border-rose-100 bg-white/70 p-4 text-sm">
                <div className="font-semibold text-stone-800">Built-in Models</div>
                <div className="leading-6 text-stone-500">{editForm.models}</div>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {CHANNEL_FIELDS.map((field) => (
                  <div key={field.key} className={field.key === "models" ? "space-y-1.5 sm:col-span-2" : "space-y-1.5"}>
                    <FieldCaption field={field} />
                    {field.key === "models" ? (
                      <Textarea
                        value={editForm.models}
                        onChange={(event) => updateEditField("models", event.target.value)}
                        placeholder={field.placeholder}
                        className="min-h-24 rounded-xl border-rose-100 bg-white"
                      />
                    ) : (
                      <Input
                        type={field.type || "text"}
                        value={editForm[field.key]}
                        onChange={(event) => updateEditField(field.key, event.target.value)}
                        placeholder={field.placeholder}
                        autoComplete={field.key === "api_key" ? "new-password" : undefined}
                        className="h-10 rounded-xl border-rose-100 bg-white"
                      />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <DialogFooter className="border-t border-rose-100 px-5 py-4 sm:px-6">
            <Button variant="outline" className="h-10 rounded-xl border-rose-100 bg-white" onClick={() => setEditingChannel(null)}>
              Cancel
            </Button>
            <Button
              className="h-10 rounded-xl bg-rose-500 text-white hover:bg-rose-600"
              disabled={Boolean(editingChannel && savingChannelId === editingChannel.id)}
              onClick={() => void handleSaveEdit()}
            >
              {editingChannel && savingChannelId === editingChannel.id ? <LoaderCircle className="size-4 animate-spin" /> : null}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

export default function ChannelsPage() {
  const { isCheckingAuth, session } = useAuthGuard(["admin"]);
  if (isCheckingAuth || !session) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoaderCircle className="size-5 animate-spin text-rose-400" />
      </div>
    );
  }
  return <ChannelsContent />;
}
