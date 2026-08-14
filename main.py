import sqlite3
import re
import csv
import hashlib
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Matplotlib integration for Tkinter
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ==========================================
# 1. DATA ACCESS OBJECT (DATABASE MANAGER)
# ==========================================
class DatabaseManager:
    """Handles all SQLite operations for Employees, Departments, Roles, and Users."""

    def __init__(self, db_name="hr_system_v2.db"):
        self.conn = sqlite3.connect(db_name)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        # Departments Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dept_name TEXT NOT NULL UNIQUE
            )
        ''')

        # Roles Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL UNIQUE
            )
        ''')

        # Master Employees Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                emp_id TEXT PRIMARY KEY,
                national_id TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                address TEXT,
                department TEXT NOT NULL,
                role_title TEXT NOT NULL,
                salary REAL NOT NULL CHECK(salary >= 0),
                status TEXT CHECK(status IN ('Active', 'Inactive')) DEFAULT 'Active'
            )
        ''')

        # Users Table (Authentication & Roles)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT CHECK(role IN ('Admin', 'Data Entry')) NOT NULL
            )
        ''')

        # Seed initial default departments if empty
        cursor.execute("SELECT COUNT(*) FROM departments")
        if cursor.fetchone()[0] == 0:
            default_depts = [("Engineering",), ("Human Resources",), ("Finance",), ("Marketing",)]
            cursor.executemany("INSERT INTO departments (dept_name) VALUES (?)", default_depts)

        # Seed initial default roles if empty
        cursor.execute("SELECT COUNT(*) FROM roles")
        if cursor.fetchone()[0] == 0:
            default_roles = [("Software Engineer",), ("HR Manager",), ("Accountant",), ("Marketing Specialist",)]
            cursor.executemany("INSERT INTO roles (role_name) VALUES (?)", default_roles)

        # Seed initial Default Admin if empty (User: admin | Pass: admin123)
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            default_admin_pass = self.hash_password("admin123")
            cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                           ("admin", default_admin_pass, "Admin"))

        self.conn.commit()

    @staticmethod
    def hash_password(password):
        """Hashes plain text password using SHA-256 for basic security."""
        return hashlib.sha256(password.encode()).hexdigest()

    def authenticate_user(self, username, password):
        """Verifies credentials and returns (username, role) or None."""
        cursor = self.conn.cursor()
        hashed = self.hash_password(password)
        cursor.execute("SELECT username, role FROM users WHERE username = ? AND password_hash = ?", (username, hashed))
        return cursor.fetchone()

    # --- USER CRUD ---
    def add_user(self, username, password, role="Data Entry"):
        cursor = self.conn.cursor()
        hashed = self.hash_password(password)
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", (username, hashed, role))
        self.conn.commit()

    def update_user(self, username, new_role, new_password=None):
        cursor = self.conn.cursor()
        if new_password:
            hashed = self.hash_password(new_password)
            cursor.execute("UPDATE users SET role = ?, password_hash = ? WHERE username = ?",
                           (new_role, hashed, username))
        else:
            cursor.execute("UPDATE users SET role = ? WHERE username = ?", (new_role, username))
        self.conn.commit()

    def get_all_users(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT username, role FROM users ORDER BY username")
        return cursor.fetchall()

    def delete_user(self, username):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        self.conn.commit()

    def get_next_emp_id(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT emp_id FROM employees WHERE emp_id LIKE 'PF %'")
        rows = cursor.fetchall()

        max_num = 0
        for (emp_id,) in rows:
            match = re.search(r'PF\s*(\d+)', emp_id)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num

        next_num = max_num + 1
        return f"PF {next_num:02d}"

    # --- DEPARTMENT CRUD ---
    def get_departments(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT dept_name FROM departments ORDER BY dept_name")
        return [row[0] for row in cursor.fetchall()]

    def add_department(self, dept_name):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO departments (dept_name) VALUES (?)", (dept_name,))
        self.conn.commit()

    def update_department(self, old_name, new_name):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE departments SET dept_name = ? WHERE dept_name = ?", (new_name, old_name))
        cursor.execute("UPDATE employees SET department = ? WHERE department = ?", (new_name, old_name))
        self.conn.commit()

    def delete_department(self, dept_name):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employees WHERE department = ?", (dept_name,))
        if cursor.fetchone()[0] > 0:
            raise Exception("Cannot delete department because employees are assigned to it.")
        cursor.execute("DELETE FROM departments WHERE dept_name = ?", (dept_name,))
        self.conn.commit()

    # --- ROLE CRUD ---
    def get_roles(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT role_name FROM roles ORDER BY role_name")
        return [row[0] for row in cursor.fetchall()]

    def add_role(self, role_name):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO roles (role_name) VALUES (?)", (role_name,))
        self.conn.commit()

    def update_role(self, old_name, new_name):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE roles SET role_name = ? WHERE role_name = ?", (new_name, old_name))
        cursor.execute("UPDATE employees SET role_title = ? WHERE role_title = ?", (new_name, old_name))
        self.conn.commit()

    def delete_role(self, role_name):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employees WHERE role_title = ?", (role_name,))
        if cursor.fetchone()[0] > 0:
            raise Exception("Cannot delete role because employees are assigned to it.")
        cursor.execute("DELETE FROM roles WHERE role_name = ?", (role_name,))
        self.conn.commit()

    # --- EMPLOYEE CRUD ---
    def add_employee(self, emp_id, national_id, name, email, address, dept, role, salary, status="Active"):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO employees (emp_id, national_id, full_name, email, address, department, role_title, salary, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (emp_id, national_id, name, email, address, dept, role, salary, status))
        self.conn.commit()

    def update_employee(self, emp_id, national_id, name, email, address, dept, role, salary, status):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE employees 
            SET national_id = ?, full_name = ?, email = ?, address = ?, department = ?, role_title = ?, salary = ?, status = ?
            WHERE emp_id = ?
        ''', (national_id, name, email, address, dept, role, salary, status, emp_id))
        self.conn.commit()

    def fetch_employees(self, search_query="", dept_filter="All"):
        cursor = self.conn.cursor()
        sql = "SELECT emp_id, full_name, national_id, email, address, department, role_title, salary, status FROM employees WHERE 1=1"
        params = []

        if search_query:
            sql += " AND (full_name LIKE ? OR email LIKE ? OR emp_id LIKE ? OR national_id LIKE ?)"
            term = f"%{search_query}%"
            params.extend([term, term, term, term])

        if dept_filter != "All":
            sql += " AND department = ?"
            params.append(dept_filter)

        sql += " ORDER BY emp_id ASC"
        cursor.execute(sql, params)
        return cursor.fetchall()

    def delete_employee(self, emp_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM employees WHERE emp_id = ?", (emp_id,))
        self.conn.commit()

    # --- DASHBOARD METRICS ---
    def get_dashboard_metrics(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employees")
        total_emp = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'Active'")
        active_emp = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'Inactive'")
        inactive_emp = cursor.fetchone()[0]

        cursor.execute('''
            SELECT department, 
                   COUNT(*) as total,
                   SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active,
                   SUM(CASE WHEN status = 'Inactive' THEN 1 ELSE 0 END) as inactive
            FROM employees 
            GROUP BY department
            ORDER BY department ASC
        ''')
        dept_stats = cursor.fetchall()

        cursor.execute('''
            SELECT role_title, 
                   COUNT(*) as total,
                   SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active,
                   SUM(CASE WHEN status = 'Inactive' THEN 1 ELSE 0 END) as inactive
            FROM employees 
            GROUP BY role_title
            ORDER BY role_title ASC
        ''')
        role_stats = cursor.fetchall()

        return {
            "total": total_emp,
            "active": active_emp,
            "inactive": inactive_emp,
            "departments": dept_stats,
            "roles": role_stats
        }

    # --- REPORT GENERATION ---
    def generate_report(self, report_type, param="All"):
        cursor = self.conn.cursor()
        sql = "SELECT emp_id, full_name, national_id, email, address, department, role_title, salary, status FROM employees"
        params = []

        if report_type == "Active Employees":
            sql += " WHERE status = 'Active' ORDER BY emp_id ASC"

        elif report_type == "Inactive Employees":
            sql += " WHERE status = 'Inactive' ORDER BY emp_id ASC"

        elif report_type == "Department Wise":
            if param and param not in ("All", "All Departments"):
                sql += " WHERE department = ? ORDER BY emp_id ASC"
                params.append(param)
            else:
                sql += " ORDER BY department ASC, emp_id ASC"

        elif report_type == "Role Wise":
            if param and param not in ("All", "All Roles"):
                sql += " WHERE role_title = ? ORDER BY emp_id ASC"
                params.append(param)
            else:
                sql += " ORDER BY role_title ASC, emp_id ASC"

        else:  # "All Employees"
            sql += " ORDER BY emp_id ASC"

        cursor.execute(sql, params)
        return cursor.fetchall()


# ==========================================
# 2. LOGIN DIALOG MODAL
# ==========================================
class LoginDialog(tk.Toplevel):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.user_data = None

        self.title("Login - HR System")
        self.geometry("350x230")
        self.resizable(False, False)

        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        tk.Label(self, text="🔒 System Login", font=("Segoe UI", 14, "bold"), fg="#2c3e50").pack(pady=10)

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Username:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.ent_user = ttk.Entry(frame, width=22)
        self.ent_user.grid(row=0, column=1, padx=5, pady=5)
        self.ent_user.focus()

        ttk.Label(frame, text="Password:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.ent_pass = ttk.Entry(frame, show="*", width=22)
        self.ent_pass.grid(row=1, column=1, padx=5, pady=5)
        self.ent_pass.bind("<Return>", lambda event: self.attempt_login())

        btn_login = ttk.Button(frame, text="Login", command=self.attempt_login)
        btn_login.grid(row=2, column=0, columnspan=2, pady=15)

    def attempt_login(self):
        username = self.ent_user.get().strip()
        password = self.ent_pass.get().strip()

        user = self.db.authenticate_user(username, password)
        if user:
            self.user_data = user
            self.destroy()
        else:
            messagebox.showerror("Login Failed", "Invalid username or password!", parent=self)

    def on_close(self):
        self.destroy()
        self.master.destroy()


# ==========================================
# 3. TKINTER GRAPHICAL USER INTERFACE
# ==========================================
class HRSystemApp:
    def __init__(self, root):
        self.root = root
        self.db = DatabaseManager()
        self.chart_type = "Bar"
        self.current_user = None
        self.current_user_role = None

        # Hide root until authenticated
        self.root.withdraw()

        self.setup_styles()
        self.start_login_session()

    def start_login_session(self):
        """Handles authentication and maximizes UI setup upon successful login."""
        self.root.withdraw()

        login_modal = LoginDialog(self.root, self.db)
        self.root.wait_window(login_modal)

        if not login_modal.user_data:
            return

        self.current_user, self.current_user_role = login_modal.user_data

        self.root.deiconify()
        self.root.title(f"HR System - Logged in as: {self.current_user} ({self.current_user_role})")
        self.root.geometry("1200x700")
        self.root.minsize(1050, 600)

        # Maximize Main Window across Operating Systems
        try:
            self.root.state('zoomed')  # Windows
        except Exception:
            try:
                self.root.attributes('-zoomed', True)  # Linux
            except Exception:
                pass

        # Clear existing widgets if re-logging in
        for widget in self.root.winfo_children():
            widget.destroy()

        self.setup_ui()
        self.open_dashboard_view()

    def logout(self):
        """Logs out current user and returns to login modal."""
        if messagebox.askyesno("Confirm Logout", "Are you sure you want to log out?"):
            self.current_user = None
            self.current_user_role = None
            self.start_login_session()

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        NAVY_HEADER = "#2c3e50"
        PRIMARY_BLUE = "#2980b9"
        PRIMARY_HOVER = "#3498db"
        BG_LIGHT = "#f4f6f9"
        CARD_BORDER = "#dcdde1"

        self.root.configure(bg=BG_LIGHT)

        self.style.configure("TFrame", background=BG_LIGHT)
        self.style.configure("TLabelframe", background=BG_LIGHT, bordercolor=CARD_BORDER)
        self.style.configure("TLabelframe.Label", background=BG_LIGHT, foreground=NAVY_HEADER,
                             font=("Segoe UI", 10, "bold"))

        self.style.configure("Header.TFrame", background=NAVY_HEADER)
        self.style.configure("Header.TLabel", background=NAVY_HEADER, foreground="#ffffff",
                             font=("Segoe UI", 16, "bold"))

        self.style.configure("TButton",
                             font=("Segoe UI", 9, "bold"),
                             foreground="#ffffff",
                             background=PRIMARY_BLUE,
                             borderwidth=0,
                             focusthickness=3,
                             padding=6)
        self.style.map("TButton",
                       background=[("active", PRIMARY_HOVER), ("disabled", "#bdc3c7")])

        self.style.configure("Treeview.Heading",
                             font=("Segoe UI", 10, "bold"),
                             background=NAVY_HEADER,
                             foreground="#ffffff")
        self.style.map("Treeview.Heading", background=[("active", PRIMARY_BLUE)])
        self.style.configure("Treeview",
                             font=("Segoe UI", 9),
                             rowheight=26,
                             background="#ffffff",
                             fieldbackground="#ffffff")

    def setup_ui(self):
        top_banner = ttk.Frame(self.root, style="Header.TFrame", padding=12)
        top_banner.pack(fill="x")
        ttk.Label(top_banner, text="🏢 HR Employee Management System", style="Header.TLabel").pack(side="left")

        # Right Action Control Frame
        right_controls = tk.Frame(top_banner, bg="#2c3e50")
        right_controls.pack(side="right")

        # Active User Info
        user_info_lbl = tk.Label(
            right_controls,
            text=f"👤 {self.current_user} [{self.current_user_role}]",
            font=("Segoe UI", 10, "bold"),
            bg="#2c3e50", fg="#ecf0f1"
        )
        user_info_lbl.pack(side="left", padx=(0, 10))

        # Logout Button
        btn_logout = tk.Button(
            right_controls,
            text="🚪 Logout",
            font=("Segoe UI", 9, "bold"),
            bg="#e74c3c", fg="#ffffff",
            activebackground="#c0392b", activeforeground="#ffffff",
            relief="flat", cursor="hand2", padx=10, pady=2,
            command=self.logout
        )
        btn_logout.pack(side="right")

        workspace_frame = ttk.Frame(self.root, padding=12)
        workspace_frame.pack(fill="both", expand=True)

        sidebar_frame = ttk.LabelFrame(workspace_frame, text=" Navigation & Actions ", padding=10)
        sidebar_frame.pack(side="left", fill="y", padx=(0, 10))

        ttk.Button(sidebar_frame, text="📌 Analytics Dashboard", command=self.open_dashboard_view, width=22).pack(
            fill="x", pady=5)
        ttk.Button(sidebar_frame, text="📋 Employee Directory", command=self.show_directory_view, width=22).pack(
            fill="x", pady=5)

        ttk.Separator(sidebar_frame, orient="horizontal").pack(fill="x", pady=10)

        ttk.Button(sidebar_frame, text="+ Add Employee", command=self.open_add_modal, width=22).pack(fill="x", pady=5)
        ttk.Button(sidebar_frame, text="✏️ Edit Selected", command=self.open_edit_modal, width=22).pack(fill="x",
                                                                                                        pady=5)

        # Restricted Action: Delete
        self.btn_delete = ttk.Button(sidebar_frame, text="🗑️ Delete Selected", command=self.delete_selected, width=22)
        self.btn_delete.pack(fill="x", pady=5)
        if self.current_user_role != "Admin":
            self.btn_delete.config(state="disabled")

        ttk.Separator(sidebar_frame, orient="horizontal").pack(fill="x", pady=10)

        ttk.Button(sidebar_frame, text="🏢 Manage Departments", command=self.open_department_manager, width=22).pack(
            fill="x", pady=5)
        ttk.Button(sidebar_frame, text="💼 Manage Roles", command=self.open_role_manager, width=22).pack(fill="x",
                                                                                                        pady=5)

        # Restricted Action: Manage Users
        if self.current_user_role == "Admin":
            ttk.Button(sidebar_frame, text="👥 Manage Users", command=self.open_user_manager, width=22).pack(fill="x",
                                                                                                            pady=5)

        ttk.Separator(sidebar_frame, orient="horizontal").pack(fill="x", pady=10)
        ttk.Button(sidebar_frame, text="📊 Reports Center", command=self.open_reports_window, width=22).pack(fill="x",
                                                                                                            pady=5)

        self.content_frame = ttk.Frame(workspace_frame)
        self.content_frame.pack(side="right", fill="both", expand=True)

    # --- DASHBOARD & DIRECTORY VIEWS ---
    def open_dashboard_view(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        metrics = self.db.get_dashboard_metrics()

        header_bar = ttk.Frame(self.content_frame)
        header_bar.pack(fill="x", pady=(0, 10))

        dash_title = tk.Label(header_bar, text="📊 Analytics Dashboard", font=("Segoe UI", 14, "bold"), bg="#f4f6f9",
                              fg="#2c3e50")
        dash_title.pack(side="left")

        btn_toggle = ttk.Button(
            header_bar,
            text=f"Switch to {'Pie Chart' if self.chart_type == 'Bar' else 'Bar Chart'}",
            command=self.toggle_chart_type
        )
        btn_toggle.pack(side="right")

        cards_frame = ttk.Frame(self.content_frame)
        cards_frame.pack(fill="x", pady=(0, 10))

        def create_card(parent, title, value, bg_color, border_color, text_color):
            card = tk.Frame(parent, bg=bg_color, padx=15, pady=12, highlightthickness=2,
                            highlightbackground=border_color)
            card.pack(side="left", fill="both", expand=True, padx=5)
            tk.Label(card, text=title, font=("Segoe UI", 10, "bold"), bg=bg_color, fg=text_color).pack(anchor="w")
            tk.Label(card, text=str(value), font=("Segoe UI", 20, "bold"), bg=bg_color, fg=text_color).pack(anchor="w",
                                                                                                            pady=(2, 0))

        create_card(cards_frame, "Total Headcount", metrics["total"], "#e8f4f8", "#3498db", "#2980b9")
        create_card(cards_frame, "Active Employees", metrics["active"], "#e8f8f5", "#2ecc71", "#27ae60")
        create_card(cards_frame, "Inactive Employees", metrics["inactive"], "#fef9e7", "#f39c12", "#d35400")

        bottom_frame = ttk.Frame(self.content_frame)
        bottom_frame.pack(fill="both", expand=True)

        chart_title = " Active Employees by Dept (Bar) " if self.chart_type == "Bar" else " Dept Distribution (Pie) "
        chart_frame = ttk.LabelFrame(bottom_frame, text=chart_title, padding=5)
        chart_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.render_department_chart(chart_frame, metrics["departments"])

        tables_frame = ttk.Frame(bottom_frame)
        tables_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        dept_frame = ttk.LabelFrame(tables_frame, text=" Department Breakdown ", padding=5)
        dept_frame.pack(fill="both", expand=True, pady=(0, 5))

        cols = ("Department", "Total", "Active", "Inactive")
        dept_tree = ttk.Treeview(dept_frame, columns=cols, show="headings", height=4)
        dept_tree.heading("Department", text="Department")
        dept_tree.column("Department", width=120, anchor="w")
        dept_tree.heading("Total", text="Total")
        dept_tree.column("Total", width=50, anchor="center")
        dept_tree.heading("Active", text="Active")
        dept_tree.column("Active", width=50, anchor="center")
        dept_tree.heading("Inactive", text="Inactive")
        dept_tree.column("Inactive", width=50, anchor="center")
        dept_tree.pack(fill="both", expand=True)

        if metrics["departments"]:
            for row in metrics["departments"]:
                dept_tree.insert("", "end", values=row)

        role_frame = ttk.LabelFrame(tables_frame, text=" Role Breakdown ", padding=5)
        role_frame.pack(fill="both", expand=True, pady=(5, 0))

        role_cols = ("Role", "Total", "Active", "Inactive")
        role_tree = ttk.Treeview(role_frame, columns=role_cols, show="headings", height=4)
        role_tree.heading("Role", text="Role Title")
        role_tree.column("Role", width=120, anchor="w")
        role_tree.heading("Total", text="Total")
        role_tree.column("Total", width=50, anchor="center")
        role_tree.heading("Active", text="Active")
        role_tree.column("Active", width=50, anchor="center")
        role_tree.heading("Inactive", text="Inactive")
        role_tree.column("Inactive", width=50, anchor="center")
        role_tree.pack(fill="both", expand=True)

        if metrics["roles"]:
            for row in metrics["roles"]:
                role_tree.insert("", "end", values=row)

    def toggle_chart_type(self):
        self.chart_type = "Pie" if self.chart_type == "Bar" else "Bar"
        self.open_dashboard_view()

    def render_department_chart(self, parent_frame, dept_data):
        fig = Figure(figsize=(5, 3.5), dpi=90)
        fig.patch.set_facecolor('#f4f6f9')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#ffffff')

        if not dept_data:
            ax.text(0.5, 0.5, "No Employee Data Available", horizontalalignment='center', verticalalignment='center')
        else:
            departments = [row[0] for row in dept_data]
            totals = [row[1] for row in dept_data]
            actives = [row[2] for row in dept_data]

            if self.chart_type == "Bar":
                import numpy as np
                x = np.arange(len(departments))
                width = 0.45
                rects = ax.bar(x, actives, width, label='Active Employees', color='#2ecc71', edgecolor='#27ae60')
                ax.set_ylabel('Active Count', fontsize=9, fontweight='bold', color='#2c3e50')
                ax.set_xticks(x)
                ax.set_xticklabels(departments, rotation=15, ha='right', fontsize=8, fontweight='bold', color='#2c3e50')
                ax.grid(axis='y', linestyle='--', alpha=0.3)
                ax.bar_label(rects, padding=2, fontsize=8, fontweight='bold')

            elif self.chart_type == "Pie":
                vibrant_colors = ['#3498db', '#2ecc71', '#e74c3c', '#f1c40f', '#9b59b6', '#e67e22']
                ax.pie(
                    totals,
                    labels=departments,
                    autopct='%1.1f%%',
                    startangle=140,
                    colors=vibrant_colors[:len(departments)],
                    textprops={'fontsize': 8, 'weight': 'bold'}
                )
                ax.axis('equal')

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def show_directory_view(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        filter_frame = ttk.LabelFrame(self.content_frame, text=" Search & Filter ", padding=8)
        filter_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(filter_frame, text="Search:").pack(side="left", padx=(5, 5))
        self.ent_search = ttk.Entry(filter_frame, width=25)
        self.ent_search.pack(side="left", padx=5)
        self.ent_search.bind("<KeyRelease>", lambda e: self.refresh_table())

        ttk.Label(filter_frame, text="Department:").pack(side="left", padx=(20, 5))
        self.cb_dept = ttk.Combobox(filter_frame, values=["All"] + self.db.get_departments(), state="readonly",
                                    width=18)
        self.cb_dept.set("All")
        self.cb_dept.pack(side="left", padx=5)
        self.cb_dept.bind("<<ComboboxSelected>>", lambda e: self.refresh_table())

        grid_frame = ttk.Frame(self.content_frame)
        grid_frame.pack(fill="both", expand=True)

        cols = (
            "Emp ID", "Full Name", "National ID", "Email", "Address", "Department", "Role Title", "Salary", "Status")
        self.tree = ttk.Treeview(grid_frame, columns=cols, show="headings", selectmode="browse")

        self.tree.tag_configure("even", background="#ffffff")
        self.tree.tag_configure("odd", background="#f8f9fa")

        col_widths = {
            "Emp ID": 80, "Full Name": 140, "National ID": 110,
            "Email": 150, "Address": 140, "Department": 110,
            "Role Title": 120, "Salary": 85, "Status": 75
        }

        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=col_widths.get(c, 100),
                             anchor="center" if c in ("Emp ID", "National ID", "Status") else "w")

        v_scrollbar = ttk.Scrollbar(grid_frame, orient="vertical", command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(grid_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

        self.tree.bind("<Double-1>", lambda event: self.open_edit_modal())
        self.refresh_table()

    def refresh_table(self):
        if not hasattr(self, 'tree') or not self.tree.winfo_exists():
            return

        for row in self.tree.get_children():
            self.tree.delete(row)

        depts = ["All"] + self.db.get_departments()
        current_dept = self.cb_dept.get()
        self.cb_dept['values'] = depts
        if current_dept not in depts:
            self.cb_dept.set("All")

        query = self.ent_search.get().strip()
        dept = self.cb_dept.get()
        records = self.db.fetch_employees(query, dept)

        for i, rec in enumerate(records):
            formatted_rec = list(rec)
            formatted_rec[7] = f"${formatted_rec[7]:,.2f}"
            row_tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", "end", values=formatted_rec, tags=(row_tag,))

    # --- MODALS & MANAGERS ---
    def open_add_modal(self):
        modal = tk.Toplevel(self.root)
        modal.title("Add New Employee")
        modal.geometry("420x560")
        modal.resizable(False, False)
        modal.grab_set()

        depts = self.db.get_departments()
        roles = self.db.get_roles()

        if not depts or not roles:
            messagebox.showwarning("Missing Config", "Please add at least one Department and Role first!", parent=modal)
            modal.destroy()
            return

        # 1. Emp ID Field (Auto-Generated)
        ttk.Label(modal, text="Emp ID (Auto-Generated):").grid(row=0, column=0, padx=15, pady=8, sticky="w")
        ent_emp_id = ttk.Entry(modal, width=28)
        ent_emp_id.insert(0, self.db.get_next_emp_id())
        ent_emp_id.config(state="disabled")
        ent_emp_id.grid(row=0, column=1, padx=15, pady=8)

        # 2. Text Input Fields
        fields = [
            ("Full Name:", ""),
            ("National ID No:", ""),
            ("Email:", ""),
            ("Address:", ""),
            ("Salary ($):", "55000")
        ]
        entries = {}

        for idx, (label_text, default_val) in enumerate(fields, start=1):
            ttk.Label(modal, text=label_text).grid(row=idx, column=0, padx=15, pady=8, sticky="w")
            ent = ttk.Entry(modal, width=28)
            ent.insert(0, default_val)
            ent.grid(row=idx, column=1, padx=15, pady=8)
            entries[label_text] = ent

        # 3. Department Combobox
        row_idx = len(fields) + 1
        ttk.Label(modal, text="Department:").grid(row=row_idx, column=0, padx=15, pady=8, sticky="w")
        cb_m_dept = ttk.Combobox(modal, values=depts, state="readonly", width=26)
        cb_m_dept.grid(row=row_idx, column=1, padx=15, pady=8)
        if depts:
            cb_m_dept.set(depts[0])

        # 4. Role Combobox
        row_idx += 1
        ttk.Label(modal, text="Role:").grid(row=row_idx, column=0, padx=15, pady=8, sticky="w")
        cb_m_role = ttk.Combobox(modal, values=roles, state="readonly", width=26)
        cb_m_role.grid(row=row_idx, column=1, padx=15, pady=8)
        if roles:
            cb_m_role.set(roles[0])

        # Set initial focus to Full Name field
        entries["Full Name:"].focus_set()

        # 5. Save Logic (Keeps Window Open)
        def save_and_reset():
            emp_id = ent_emp_id.get().strip()
            name = entries["Full Name:"].get().strip()
            national_id = entries["National ID No:"].get().strip()
            email = entries["Email:"].get().strip()
            address = entries["Address:"].get().strip()
            salary_raw = entries["Salary ($):"].get().strip()
            dept = cb_m_dept.get()
            role = cb_m_role.get()

            # Input Validation
            if not name or not national_id or not email:
                messagebox.showerror("Error", "Name, National ID, and Email are required!", parent=modal)
                return

            try:
                salary = float(salary_raw)
            except ValueError:
                messagebox.showerror("Error", "Salary must be a valid number!", parent=modal)
                return

            try:
                # Save into SQLite Database
                self.db.add_employee(emp_id, national_id, name, email, address, dept, role, salary)

                # Show Confirmation Message
                messagebox.showinfo("Success", f"Employee {emp_id} added successfully!\nReady for next entry.", parent=modal)

                # --- RESET FORM FOR NEXT ENTRY ---
                # 1. Generate next ID and update field
                ent_emp_id.config(state="normal")
                ent_emp_id.delete(0, tk.END)
                ent_emp_id.insert(0, self.db.get_next_emp_id())
                ent_emp_id.config(state="disabled")

                # 2. Clear user inputs
                entries["Full Name:"].delete(0, tk.END)
                entries["National ID No:"].delete(0, tk.END)
                entries["Email:"].delete(0, tk.END)
                entries["Address:"].delete(0, tk.END)
                entries["Salary ($):"].delete(0, tk.END)
                entries["Salary ($):"].insert(0, "55000")

                # 3. Return cursor back to Full Name
                entries["Full Name:"].focus_set()

                # 4. Refresh directory if directory view is currently open
                self.refresh_table()

            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to add employee:\n{e}", parent=modal)

        # 6. Action Buttons
        btn_frame = ttk.Frame(modal)
        btn_frame.grid(row=row_idx + 1, column=0, columnspan=2, pady=15)

        btn_save = ttk.Button(btn_frame, text="💾 Save & Add Next", command=save_and_reset)
        btn_save.pack(side="left", padx=5)

        btn_close = ttk.Button(btn_frame, text="❌ Close", command=modal.destroy)
        btn_close.pack(side="left", padx=5)

    def open_edit_modal(self):
        if not hasattr(self, 'tree') or not self.tree.selection():
            messagebox.showwarning("Select Record", "Please select an employee from the Directory view first!")
            return

        selected_item = self.tree.selection()[0]
        rec = self.tree.item(selected_item, "values")

        modal = tk.Toplevel(self.root)
        modal.title(f"Edit Employee - {rec[0]}")
        modal.geometry("420x560")
        modal.resizable(False, False)
        modal.grab_set()

        depts = self.db.get_departments()
        roles = self.db.get_roles()

        ttk.Label(modal, text="Emp ID:").grid(row=0, column=0, padx=15, pady=8, sticky="w")
        ent_emp_id = ttk.Entry(modal, width=28)
        ent_emp_id.insert(0, rec[0])
        ent_emp_id.config(state="disabled")
        ent_emp_id.grid(row=0, column=1, padx=15, pady=8)

        fields = [
            ("Full Name:", rec[1]),
            ("National ID No:", rec[2]),
            ("Email:", rec[3]),
            ("Address:", rec[4]),
            ("Salary ($):", rec[7].replace("$", "").replace(",", ""))
        ]
        entries = {}

        for idx, (label_text, val) in enumerate(fields, start=1):
            ttk.Label(modal, text=label_text).grid(row=idx, column=0, padx=15, pady=8, sticky="w")
            ent = ttk.Entry(modal, width=28)
            ent.insert(0, val)
            ent.grid(row=idx, column=1, padx=15, pady=8)
            entries[label_text] = ent

        row_idx = len(fields) + 1
        ttk.Label(modal, text="Department:").grid(row=row_idx, column=0, padx=15, pady=8, sticky="w")
        cb_m_dept = ttk.Combobox(modal, values=depts, state="readonly", width=26)
        cb_m_dept.set(rec[5])
        cb_m_dept.grid(row=row_idx, column=1, padx=15, pady=8)

        row_idx += 1
        ttk.Label(modal, text="Role:").grid(row=row_idx, column=0, padx=15, pady=8, sticky="w")
        cb_m_role = ttk.Combobox(modal, values=roles, state="readonly", width=26)
        cb_m_role.set(rec[6])
        cb_m_role.grid(row=row_idx, column=1, padx=15, pady=8)

        row_idx += 1
        ttk.Label(modal, text="Status:").grid(row=row_idx, column=0, padx=15, pady=8, sticky="w")
        cb_m_status = ttk.Combobox(modal, values=["Active", "Inactive"], state="readonly", width=26)
        cb_m_status.set(rec[8])
        cb_m_status.grid(row=row_idx, column=1, padx=15, pady=8)

        def save_changes():
            try:
                salary = float(entries["Salary ($):"].get().strip())
                self.db.update_employee(
                    rec[0],
                    entries["National ID No:"].get().strip(),
                    entries["Full Name:"].get().strip(),
                    entries["Email:"].get().strip(),
                    entries["Address:"].get().strip(),
                    cb_m_dept.get(),
                    cb_m_role.get(),
                    salary,
                    cb_m_status.get()
                )
                messagebox.showinfo("Success", "Employee updated successfully!", parent=modal)
                modal.destroy()
                self.refresh_table()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update employee:\n{e}", parent=modal)

        ttk.Button(modal, text="💾 Save Changes", command=save_changes).grid(row=row_idx + 1, column=0, columnspan=2, pady=15)

    def delete_selected(self):
        if not hasattr(self, 'tree') or not self.tree.selection():
            messagebox.showwarning("Select Record", "Please select an employee from the Directory view first!")
            return

        selected_item = self.tree.selection()[0]
        emp_id = self.tree.item(selected_item, "values")[0]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete employee {emp_id}?"):
            try:
                self.db.delete_employee(emp_id)
                self.refresh_table()
                messagebox.showinfo("Deleted", f"Employee {emp_id} removed.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete employee:\n{e}")

    def open_department_manager(self):
        modal = tk.Toplevel(self.root)
        modal.title("Manage Departments")
        modal.geometry("380x320")
        modal.grab_set()

        ttk.Label(modal, text="Add Department:").pack(anchor="w", padx=15, pady=(10, 2))
        frame_add = ttk.Frame(modal)
        frame_add.pack(fill="x", padx=15)

        ent_dept = ttk.Entry(frame_add, width=22)
        ent_dept.pack(side="left", padx=(0, 5))

        def add_dept():
            name = ent_dept.get().strip()
            if name:
                try:
                    self.db.add_department(name)
                    ent_dept.delete(0, tk.END)
                    load_depts()
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=modal)

        ttk.Button(frame_add, text="Add", command=add_dept).pack(side="left")

        listbox = tk.Listbox(modal, height=8)
        listbox.pack(fill="both", expand=True, padx=15, pady=10)

        def load_depts():
            listbox.delete(0, tk.END)
            for d in self.db.get_departments():
                listbox.insert(tk.END, d)

        def del_dept():
            sel = listbox.curselection()
            if sel:
                d_name = listbox.get(sel[0])
                try:
                    self.db.delete_department(d_name)
                    load_depts()
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=modal)

        ttk.Button(modal, text="Delete Selected", command=del_dept).pack(pady=(0, 10))
        load_depts()

    def open_role_manager(self):
        modal = tk.Toplevel(self.root)
        modal.title("Manage Roles")
        modal.geometry("380x320")
        modal.grab_set()

        ttk.Label(modal, text="Add Role Title:").pack(anchor="w", padx=15, pady=(10, 2))
        frame_add = ttk.Frame(modal)
        frame_add.pack(fill="x", padx=15)

        ent_role = ttk.Entry(frame_add, width=22)
        ent_role.pack(side="left", padx=(0, 5))

        def add_role():
            name = ent_role.get().strip()
            if name:
                try:
                    self.db.add_role(name)
                    ent_role.delete(0, tk.END)
                    load_roles()
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=modal)

        ttk.Button(frame_add, text="Add", command=add_role).pack(side="left")

        listbox = tk.Listbox(modal, height=8)
        listbox.pack(fill="both", expand=True, padx=15, pady=10)

        def load_roles():
            listbox.delete(0, tk.END)
            for r in self.db.get_roles():
                listbox.insert(tk.END, r)

        def del_role():
            sel = listbox.curselection()
            if sel:
                r_name = listbox.get(sel[0])
                try:
                    self.db.delete_role(r_name)
                    load_roles()
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=modal)

        ttk.Button(modal, text="Delete Selected", command=del_role).pack(pady=(0, 10))
        load_roles()

    def open_user_manager(self):
        modal = tk.Toplevel(self.root)
        modal.title("Manage System Users")
        modal.geometry("400x350")
        modal.grab_set()

        ttk.Label(modal, text="Add New User", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=15, pady=(10, 5))

        frame_form = ttk.Frame(modal, padding=5)
        frame_form.pack(fill="x", padx=10)

        ttk.Label(frame_form, text="Username:").grid(row=0, column=0, padx=5, pady=2)
        ent_u = ttk.Entry(frame_form, width=15)
        ent_u.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(frame_form, text="Password:").grid(row=1, column=0, padx=5, pady=2)
        ent_p = ttk.Entry(frame_form, show="*", width=15)
        ent_p.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(frame_form, text="Role:").grid(row=2, column=0, padx=5, pady=2)
        cb_r = ttk.Combobox(frame_form, values=["Data Entry", "Admin"], state="readonly", width=13)
        cb_r.set("Data Entry")
        cb_r.grid(row=2, column=1, padx=5, pady=2)

        def add_user():
            u = ent_u.get().strip()
            p = ent_p.get().strip()
            r = cb_r.get()
            if u and p:
                try:
                    self.db.add_user(u, p, r)
                    ent_u.delete(0, tk.END)
                    ent_p.delete(0, tk.END)
                    load_users()
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=modal)

        ttk.Button(frame_form, text="Add User", command=add_user).grid(row=3, column=0, columnspan=2, pady=5)

        tree = ttk.Treeview(modal, columns=("Username", "Role"), show="headings", height=5)
        tree.heading("Username", text="Username")
        tree.heading("Role", text="Role")
        tree.pack(fill="both", expand=True, padx=15, pady=5)

        def load_users():
            for row in tree.get_children():
                tree.delete(row)
            for u in self.db.get_all_users():
                tree.insert("", "end", values=u)

        load_users()

    # --- REPORTS CENTER WITH LIVE FILTER DETAILS PREVIEW ---
    def open_reports_window(self):
        modal = tk.Toplevel(self.root)
        modal.title("Reports Center - Preview & Export")
        modal.geometry("800x530")
        modal.minsize(700, 450)
        modal.grab_set()

        ttk.Label(modal, text="📊 Export & Preview Employee Reports", font=("Segoe UI", 12, "bold")).pack(pady=(12, 5))

        # Filter Selection Controls Header
        frame_controls = ttk.Frame(modal, padding=10)
        frame_controls.pack(fill="x")

        # 1. Primary Report Type Dropdown
        ttk.Label(frame_controls, text="Report Type:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        report_types = [
            "All Employees",
            "Active Employees",
            "Inactive Employees",
            "Department Wise",
            "Role Wise"
        ]
        cb_type = ttk.Combobox(frame_controls, values=report_types, state="readonly", width=22)
        cb_type.set("All Employees")
        cb_type.grid(row=0, column=1, padx=5, pady=5)

        # 2. Secondary Dynamic Filter Dropdown (Dept / Role)
        lbl_filter = ttk.Label(frame_controls, text="Filter By:")
        lbl_filter.grid(row=0, column=2, padx=(20, 5), pady=5, sticky="w")

        cb_filter = ttk.Combobox(frame_controls, state="disabled", width=22)
        cb_filter.grid(row=0, column=3, padx=5, pady=5)

        # Active Filter Status Line
        lbl_status = ttk.Label(
            modal,
            text="",
            font=("Segoe UI", 9, "bold"),
            foreground="#2980b9"
        )
        lbl_status.pack(pady=(2, 6))

        # Live Filtered Details Preview Table
        frame_preview = ttk.LabelFrame(modal, text=" Filtered Employee Details Preview ", padding=6)
        frame_preview.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        cols = ("Emp ID", "Full Name", "National ID", "Email", "Department", "Role", "Salary", "Status")
        tree_preview = ttk.Treeview(frame_preview, columns=cols, show="headings", height=8)

        col_widths = {
            "Emp ID": 70, "Full Name": 130, "National ID": 100,
            "Email": 140, "Department": 110, "Role": 120,
            "Salary": 85, "Status": 70
        }
        for c in cols:
            tree_preview.heading(c, text=c)
            tree_preview.column(c, width=col_widths.get(c, 90), anchor="center" if c in ("Emp ID", "National ID", "Status") else "w")

        v_scroll = ttk.Scrollbar(frame_preview, orient="vertical", command=tree_preview.yview)
        tree_preview.configure(yscrollcommand=v_scroll.set)
        tree_preview.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        # Function to Update Preview Table & Status Banner dynamically
        def update_filtered_preview(event=None):
            for item in tree_preview.get_children():
                tree_preview.delete(item)

            rep_type = cb_type.get()
            param = cb_filter.get() if cb_filter["state"] != "disabled" else "All"
            data = self.db.generate_report(rep_type, param)

            # Update status text line with active filter criteria
            filter_text = f" -> {param}" if param and param != "All" else ""
            lbl_status.config(
                text=f"🔍 Applied Criteria: [{rep_type}{filter_text}] | Total Records Found: {len(data)}"
            )

            # Populate preview table rows
            for row in data:
                display_row = [
                    row[0],             # Emp ID
                    row[1],             # Full Name
                    row[2],             # National ID
                    row[3],             # Email
                    row[5],             # Department
                    row[6],             # Role
                    f"${row[7]:,.2f}",  # Salary
                    row[8]              # Status
                ]
                tree_preview.insert("", "end", values=display_row)

        def on_report_type_change(event=None):
            selected = cb_type.get()
            if selected == "Department Wise":
                lbl_filter.config(text="Department:")
                depts = ["All Departments"] + self.db.get_departments()
                cb_filter.config(state="readonly", values=depts)
                cb_filter.set("All Departments")
            elif selected == "Role Wise":
                lbl_filter.config(text="Role:")
                roles = ["All Roles"] + self.db.get_roles()
                cb_filter.config(state="readonly", values=roles)
                cb_filter.set("All Roles")
            else:
                lbl_filter.config(text="Filter By:")
                cb_filter.config(state="disabled")
                cb_filter.set("")

            update_filtered_preview()

        cb_type.bind("<<ComboboxSelected>>", on_report_type_change)
        cb_filter.bind("<<ComboboxSelected>>", update_filtered_preview)

        # Initial loading trigger
        on_report_type_change()

        # CSV Export with Header Filter Summary Details
        def export_csv():
            rep_type = cb_type.get()
            param = cb_filter.get() if cb_filter["state"] != "disabled" else "All"
            data = self.db.generate_report(rep_type, param)

            if not data:
                messagebox.showwarning("No Data", "No records found for the selected report criteria.", parent=modal)
                return

            default_filename = f"{rep_type.replace(' ', '_').lower()}_report.csv"

            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Files", "*.csv")],
                title="Save Report As",
                initialfile=default_filename,
                parent=modal
            )

            if file_path:
                try:
                    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)

                        # Write Filter Metadata at top of file
                        writer.writerow(["# EMPLOYEE REPORT & FILTER DETAILS"])
                        writer.writerow(["# Report Type:", rep_type])
                        writer.writerow(["# Filter Parameter:", param])
                        writer.writerow(["# Generated Date:", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                        writer.writerow(["# Generated By User:", self.current_user])
                        writer.writerow(["# Total Matching Records:", len(data)])
                        writer.writerow([])  # Blank separator line

                        # Write CSV Headers & Records
                        writer.writerow(["Emp ID", "Full Name", "National ID", "Email", "Address", "Department", "Role", "Salary", "Status"])
                        writer.writerows(data)

                    messagebox.showinfo("Export Successful", f"Report successfully saved to:\n{file_path}", parent=modal)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export CSV:\n{e}", parent=modal)

        # Footer Actions
        btn_frame = ttk.Frame(modal)
        btn_frame.pack(fill="x", pady=(0, 12))

        btn_export = ttk.Button(btn_frame, text="📄 Export Filtered Report to CSV", command=export_csv)
        btn_export.pack(side="top")


# ==========================================
# 4. APPLICATION ENTRY POINT
# ==========================================
if __name__ == "__main__":
    root = tk.Tk()
    app = HRSystemApp(root)
    root.mainloop()