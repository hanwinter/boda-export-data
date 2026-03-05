import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Checkbox,
  DatePicker,
  Divider,
  Form,
  Input,
  message,
  Modal,
  Select,
  Space,
  Table,
  Tag
} from "antd";
import { api, TOKEN_KEY } from "./api";

const { RangePicker } = DatePicker;
const statusOptions = ["待总检", "已总检", "已终检"];

function GroupBlock({ group }) {
  const detailColumns = [
    { title: "参数名称", dataIndex: "item_name", key: "item_name", width: 220 },
    {
      title: "结果值",
      dataIndex: "result_value",
      key: "result_value",
      width: 140,
      render: (value, row) => (row.is_abnormal ? <span className="abnormal">{value}</span> : value)
    },
    { title: "单位", dataIndex: "unit", key: "unit", width: 120 },
    { title: "参考范围", dataIndex: "ref_range", key: "ref_range", width: 180 },
    {
      title: "异常",
      dataIndex: "abnormal_flag",
      key: "abnormal_flag",
      width: 100,
      render: (value, row) =>
        row.is_abnormal ? <Tag color="red">{value || "异常"}</Tag> : <Tag color="default">正常</Tag>
    }
  ];

  return (
    <div className="group-block">
      <div className="group-header">
        <span className={group.group_is_abnormal ? "group-name abnormal" : "group-name"}>{group.group_name}</span>
        {group.group_is_abnormal ? (
          <Tag color="red">异常 {group.abnormal_count} 项</Tag>
        ) : (
          <Tag color="success">正常</Tag>
        )}
      </div>
      <Table
        size="small"
        rowKey={(item, index) => `${group.group_name}-${item.item_name}-${index}`}
        columns={detailColumns}
        dataSource={group.items || []}
        pagination={false}
        bordered
      />
    </div>
  );
}

function LoginCard({ onLogin }) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      const response = await api.post("/api/auth/login", values);
      localStorage.setItem(TOKEN_KEY, response.data.access_token);
      onLogin(response.data.user);
      message.success("登录成功");
    } catch (err) {
      if (err?.response?.status === 401) {
        message.error("用户名或密码错误");
      } else if (!err?.errorFields) {
        message.error("登录失败，请检查后端服务");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-wrap">
      <Card className="login-card" bordered={false}>
        <h2 className="title">用户登录</h2>
        <p className="subtitle">默认测试账号：admin/admin123 或 viewer/viewer123</p>
        <Form form={form} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input placeholder="请输入用户名" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password placeholder="请输入密码" />
          </Form.Item>
          <Button type="primary" block onClick={submit} loading={loading}>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  );
}

export function App() {
  const [user, setUser] = useState(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [orgs, setOrgs] = useState([]);
  const [projectGroups, setProjectGroups] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [userModalOpen, setUserModalOpen] = useState(false);

  const [form] = Form.useForm();
  const [exportForm] = Form.useForm();
  const [createUserForm] = Form.useForm();

  const columns = useMemo(
    () => [
      { title: "单位", dataIndex: "org_name", key: "org_name", width: 140, fixed: "left" },
      { title: "姓名", dataIndex: "person_name", key: "person_name", width: 100, fixed: "left" },
      { title: "性别", dataIndex: "gender", key: "gender", width: 80 },
      { title: "证件号", dataIndex: "id_no", key: "id_no", width: 190 },
      { title: "电话", dataIndex: "phone", key: "phone", width: 130 },
      { title: "体检编号", dataIndex: "exam_no", key: "exam_no", width: 150 },
      { title: "汇总日期", dataIndex: "summary_date", key: "summary_date", width: 120 },
      { title: "终检日期", dataIndex: "final_date", key: "final_date", width: 120 },
      {
        title: "体检状态",
        dataIndex: "exam_status",
        key: "exam_status",
        width: 120,
        render: (value) => {
          const color = value === "已终检" ? "success" : value === "已总检" ? "processing" : "default";
          return <Tag color={color}>{value}</Tag>;
        }
      },
      {
        title: "整体异常",
        dataIndex: "has_abnormal",
        key: "has_abnormal",
        width: 100,
        render: (value) => (value ? <Tag color="red">异常</Tag> : <Tag color="success">正常</Tag>)
      }
    ],
    []
  );

  const userColumns = [
    { title: "用户名", dataIndex: "username", key: "username" },
    { title: "角色", dataIndex: "role", key: "role" },
    {
      title: "状态",
      dataIndex: "is_active",
      key: "is_active",
      render: (value) => (value ? <Tag color="success">启用</Tag> : <Tag color="default">禁用</Tag>)
    },
    {
      title: "操作",
      key: "actions",
      render: (_, row) => (
        <Space>
          <Button size="small" onClick={() => toggleUserStatus(row)} disabled={row.username === user?.username}>
            {row.is_active ? "禁用" : "启用"}
          </Button>
          <Button size="small" onClick={() => resetUserPassword(row.username)}>
            重置密码
          </Button>
        </Space>
      )
    }
  ];

  const buildParams = (page = pagination.current, pageSize = pagination.pageSize) => {
    const values = form.getFieldsValue();
    const params = { page, page_size: pageSize, only_abnormal: !!values.only_abnormal };
    if (values.org_id) params.org_id = values.org_id;
    if (values.keyword) params.keyword = values.keyword.trim();
    if (values.exam_no) params.exam_no = values.exam_no.trim();
    if (values.exam_status) params.exam_status = values.exam_status;
    if (values.summary_date?.length === 2) {
      params.summary_start_date = values.summary_date[0].format("YYYY-MM-DD");
      params.summary_end_date = values.summary_date[1].format("YYYY-MM-DD");
    }
    if (values.final_date?.length === 2) {
      params.final_start_date = values.final_date[0].format("YYYY-MM-DD");
      params.final_end_date = values.final_date[1].format("YYYY-MM-DD");
    }
    return params;
  };

  const handleAuthError = () => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    message.warning("登录已失效，请重新登录");
  };

  const checkMe = async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setCheckingAuth(false);
      return;
    }
    try {
      const response = await api.get("/api/auth/me");
      setUser(response.data);
    } catch {
      localStorage.removeItem(TOKEN_KEY);
    } finally {
      setCheckingAuth(false);
    }
  };

  const loadUsers = async () => {
    if (user?.role !== "admin") return;
    try {
      const response = await api.get("/api/users");
      setUsers(response.data || []);
    } catch (err) {
      if (err?.response?.status === 401) return handleAuthError();
      if (err?.response?.status === 403) return message.error("仅管理员可查看用户管理");
      message.error("用户列表加载失败");
    }
  };

  const createUser = async () => {
    try {
      const values = await createUserForm.validateFields();
      await api.post("/api/users", values);
      message.success("用户创建成功");
      createUserForm.resetFields();
      loadUsers();
    } catch (err) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || "创建用户失败");
    }
  };

  const toggleUserStatus = async (row) => {
    try {
      await api.patch(`/api/users/${row.username}/status`, { is_active: !row.is_active });
      message.success("用户状态已更新");
      loadUsers();
    } catch (err) {
      message.error(err?.response?.data?.detail || "更新失败");
    }
  };

  const resetUserPassword = async (username) => {
    try {
      await api.post(`/api/users/${username}/reset-password`, { new_password: "123456" });
      message.success(`用户 ${username} 密码已重置为 123456`);
    } catch (err) {
      message.error(err?.response?.data?.detail || "重置密码失败");
    }
  };

  const loadOrgs = async () => {
    try {
      const response = await api.get("/api/orgs");
      setOrgs(response.data || []);
    } catch (err) {
      if (err?.response?.status === 401) return handleAuthError();
      message.error("单位列表加载失败");
    }
  };

  const loadProjectGroups = async () => {
    try {
      const response = await api.get("/api/project-groups");
      setProjectGroups(response.data || []);
    } catch (err) {
      if (err?.response?.status === 401) return handleAuthError();
      message.error("项目组加载失败");
    }
  };

  const loadRecords = async (page = pagination.current, pageSize = pagination.pageSize) => {
    setLoading(true);
    try {
      const response = await api.get("/api/records", { params: buildParams(page, pageSize) });
      setRecords(response.data.items || []);
      setTotal(response.data.total || 0);
      setPagination({ current: page, pageSize });
    } catch (err) {
      if (err?.response?.status === 401) return handleAuthError();
      message.error("数据加载失败");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => loadRecords(1, pagination.pageSize);

  const handleReset = () => {
    form.resetFields();
    form.setFieldsValue({ only_abnormal: false });
    loadRecords(1, pagination.pageSize);
  };

  const openExportModal = () => {
    exportForm.setFieldsValue({ export_dir: "", selected_groups: [] });
    setExportModalOpen(true);
  };

  const openUserModal = () => {
    setUserModalOpen(true);
    loadUsers();
  };

  const submitExport = async () => {
    try {
      const exportValues = await exportForm.validateFields();
      const values = form.getFieldsValue();
      setExporting(true);
      const payload = {
        org_id: values.org_id || null,
        keyword: values.keyword?.trim() || null,
        exam_no: values.exam_no?.trim() || null,
        exam_status: values.exam_status || null,
        summary_start_date: values.summary_date?.[0]?.format("YYYY-MM-DD") || null,
        summary_end_date: values.summary_date?.[1]?.format("YYYY-MM-DD") || null,
        final_start_date: values.final_date?.[0]?.format("YYYY-MM-DD") || null,
        final_end_date: values.final_date?.[1]?.format("YYYY-MM-DD") || null,
        only_abnormal: !!values.only_abnormal,
        export_dir: exportValues.export_dir?.trim() || null,
        selected_groups: exportValues.selected_groups?.length ? exportValues.selected_groups : null
      };

      const response = await api.post("/api/export", payload);
      message.success(`导出成功：${response.data.file_name}`);
      message.info(`导出路径：${response.data.file_path}`);
      setExportModalOpen(false);
    } catch (err) {
      if (err?.errorFields) return;
      if (err?.response?.status === 401) return handleAuthError();
      message.error("导出失败");
    } finally {
      setExporting(false);
    }
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    setRecords([]);
  };

  useEffect(() => {
    checkMe();
  }, []);

  useEffect(() => {
    if (!user) return;
    form.setFieldsValue({ only_abnormal: false });
    loadOrgs();
    loadProjectGroups();
    loadRecords(1, pagination.pageSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  if (checkingAuth) {
    return <div className="login-wrap">正在检查登录状态...</div>;
  }

  if (!user) {
    return <LoginCard onLogin={setUser} />;
  }

  return (
    <div className="page">
      <Card className="card" bordered={false}>
        <div className="header-row">
          <div>
            <h1 className="title">体检数据导出平台</h1>
            <p className="subtitle">主表按人员+体检编号展示，展开后一次显示项目组与参数明细</p>
          </div>
          <Space>
            <Tag color="blue">{user.username}</Tag>
            <Tag>{user.role}</Tag>
            {user.role === "admin" && <Button onClick={openUserModal}>用户管理</Button>}
            <Button onClick={logout}>退出登录</Button>
          </Space>
        </div>

        <Form form={form} layout="inline" className="filters">
          <Form.Item name="org_id" label="单位">
            <Select
              placeholder="请选择单位"
              allowClear
              showSearch
              optionFilterProp="label"
              filterOption={(input, option) =>
                String(option?.label || "").toLowerCase().includes(input.toLowerCase())
              }
              style={{ width: 170 }}
              options={orgs.map((org) => ({ value: org.org_id, label: org.org_name }))}
            />
          </Form.Item>

          <Form.Item name="keyword" label="人员">
            <Input placeholder="姓名/证件号" allowClear style={{ width: 160 }} />
          </Form.Item>

          <Form.Item name="exam_no" label="体检编号">
            <Input placeholder="请输入体检编号" allowClear style={{ width: 170 }} />
          </Form.Item>

          <Form.Item name="exam_status" label="体检状态">
            <Select
              placeholder="请选择状态"
              allowClear
              style={{ width: 140 }}
              options={statusOptions.map((status) => ({ value: status, label: status }))}
            />
          </Form.Item>

          <Form.Item name="summary_date" label="汇总日期">
            <RangePicker allowEmpty={[true, true]} />
          </Form.Item>

          <Form.Item name="final_date" label="终检日期">
            <RangePicker allowEmpty={[true, true]} />
          </Form.Item>

          <Form.Item name="only_abnormal" valuePropName="checked">
            <Checkbox>仅看异常</Checkbox>
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" onClick={handleSearch}>查询</Button>
              <Button onClick={handleReset}>重置</Button>
              <Button onClick={openExportModal}>导出Excel</Button>
            </Space>
          </Form.Item>
        </Form>

        <Divider style={{ margin: "10px 0 14px" }} />

        <Table
          rowKey="record_id"
          loading={loading}
          columns={columns}
          dataSource={records}
          scroll={{ x: 1450 }}
          expandable={{
            expandedRowRender: (record) => (
              <div className="expand-wrap">
                {(record.project_groups || []).map((group) => (
                  <GroupBlock key={`${record.record_id}-${group.group_name}`} group={group} />
                ))}
              </div>
            ),
            rowExpandable: (record) => (record.project_groups || []).length > 0
          }}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: ["20", "50", "100"],
            showTotal: (count) => `共 ${count} 条`,
            onChange: (page, pageSize) => loadRecords(page, pageSize)
          }}
        />

        <Modal
          title="导出设置"
          open={exportModalOpen}
          onCancel={() => setExportModalOpen(false)}
          onOk={submitExport}
          okText="确认导出"
          confirmLoading={exporting}
          width={640}
        >
          <Form form={exportForm} layout="vertical">
            <Form.Item name="export_dir" label="导出目录（可选）" extra="留空则使用默认 exports 目录">
              <Input placeholder="例如：D:\\ExportFiles\\HealthData" />
            </Form.Item>

            <Form.Item
              name="selected_groups"
              label="导出组合项目（可多选）"
              extra="选择项目组后会导出该组下全部细项；不选则导出全部"
            >
              <Select
                mode="multiple"
                allowClear
                placeholder="请选择项目组"
                options={projectGroups.map((name) => ({ value: name, label: name }))}
              />
            </Form.Item>
          </Form>
        </Modal>

        <Modal
          title="用户管理"
          open={userModalOpen}
          onCancel={() => setUserModalOpen(false)}
          footer={null}
          width={820}
        >
          <Card size="small" title="新增用户" className="user-create-card">
            <Form form={createUserForm} layout="inline">
              <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
                <Input placeholder="用户名" style={{ width: 180 }} />
              </Form.Item>
              <Form.Item name="password" rules={[{ required: true, message: "请输入初始密码" }]}>
                <Input.Password placeholder="初始密码" style={{ width: 180 }} />
              </Form.Item>
              <Form.Item name="role" initialValue="viewer">
                <Select
                  style={{ width: 120 }}
                  options={[
                    { value: "viewer", label: "viewer" },
                    { value: "admin", label: "admin" }
                  ]}
                />
              </Form.Item>
              <Button type="primary" onClick={createUser}>创建</Button>
            </Form>
          </Card>

          <Divider />

          <Table rowKey="username" columns={userColumns} dataSource={users} pagination={false} />
          <div className="user-tip">重置密码默认值为 `123456`。</div>
        </Modal>
      </Card>
    </div>
  );
}


