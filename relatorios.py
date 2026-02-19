import streamlit as st
import pandas as pd
import io
from fpdf import FPDF
import datetime
import tempfile
import os

# --- GERADOR DE PDF ---
class PDFReport(FPDF):
    def __init__(self, titulo, usuario):
        super().__init__()
        self.titulo = titulo
        self.usuario = usuario
        self.data_emissao = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    def header(self):
        # Logo
        try:
            # Tenta centralizar a logo ou colocar no canto
            self.image('logo-brasil-digital.png', 10, 8, 33)
        except: pass
        
        # Fonte
        self.set_font('Arial', 'B', 15)
        self.cell(80)
        self.cell(30, 10, self.titulo, 0, 0, 'C')
        self.ln(20)
        
        # Linha divisória verde
        self.set_draw_color(0, 166, 81) # Verde Brasil
        self.set_line_width(1)
        self.line(10, 25, 200, 25)
        
        # Info
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Gerado por: {self.usuario} | Em: {self.data_emissao}', 0, 1, 'R')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def gerar_pdf_analitico(df, metrics, figures, user_name):
    pdf = PDFReport("Relatório Financeiro", user_name)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # 1. Cartões de Métricas
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 90, 167) # Azul Brasil
    pdf.cell(0, 10, 'Resumo Geral', 0, 1)
    pdf.set_text_color(0, 0, 0) # Preto
    
    pdf.set_font('Arial', '', 10)
    col_w = 45
    for key, value in metrics.items():
        pdf.cell(col_w, 10, f"{key}", 1, 0, 'C')
    pdf.ln()
    pdf.set_font('Arial', 'B', 11)
    for key, value in metrics.items():
        pdf.cell(col_w, 10, f"{value}", 1, 0, 'C')
    pdf.ln(15)

    # 2. Gráficos
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 90, 167)
    pdf.cell(0, 10, 'Análise Gráfica', 0, 1)
    pdf.set_text_color(0, 0, 0)
    
    try:
        with tempfile.TemporaryDirectory() as tmpdirname:
            for i, fig in enumerate(figures):
                if fig:
                    # --- CORREÇÃO DO FUNDO PRETO ---
                    # Força o template branco e remove transparência
                    fig.update_layout(
                        template="plotly_white",
                        paper_bgcolor="white",
                        plot_bgcolor="white",
                        font=dict(color="black")
                    )
                    
                    img_path = os.path.join(tmpdirname, f"chart_{i}.png")
                    # Aumenta scale para melhor resolução
                    fig.write_image(img_path, width=800, height=450, scale=2)
                    
                    # Verifica se cabe na página, senão cria nova
                    if pdf.get_y() > 200:
                        pdf.add_page()
                    
                    pdf.image(img_path, x=10, w=190)
                    pdf.ln(5)
    except Exception as e:
        pdf.set_font('Arial', 'I', 10)
        pdf.set_text_color(255, 0, 0)
        pdf.cell(0, 10, f"Erro ao gerar gráficos: {e}", 0, 1)
        pdf.set_text_color(0, 0, 0)

    # 3. Tabela de Detalhes (Top 50)
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 90, 167)
    pdf.cell(0, 10, 'Detalhamento (Top 50 Registros)', 0, 1)
    pdf.set_text_color(0, 0, 0)
    
    pdf.set_font('Arial', 'B', 7)
    cols = ['Nome', 'Cargo', 'Empresa', 'Valor (R$)']
    w_cols = [60, 50, 50, 30]
    
    for i, c in enumerate(cols):
        pdf.cell(w_cols[i], 7, c, 1, 0, 'C')
    pdf.ln()
    
    pdf.set_font('Arial', '', 7)
    df_top = df.head(50)
    
    for _, row in df_top.iterrows():
        try:
            pdf.cell(w_cols[0], 6, str(row['Nome'])[:35], 1)
            pdf.cell(w_cols[1], 6, str(row['Cargo'])[:30], 1)
            pdf.cell(w_cols[2], 6, str(row['Empresa'])[:25], 1)
            pdf.cell(w_cols[3], 6, f"{row['Valor (R$)']:,.2f}", 1, 0, 'R')
            pdf.ln()
        except: pass

    return pdf.output(dest='S').encode('latin-1')

# --- GERADOR DE EXCEL ---
def gerar_excel_personalizado(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Base de Dados')
        workbook = writer.book
        worksheet = writer.sheets['Base de Dados']
        
        # Formatos
        money_fmt = workbook.add_format({'num_format': 'R$ #,##0.00'})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#005AA7', 'font_color': 'white', 'border': 1})
        
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 20)
            
        try:
            col_idx = df.columns.get_loc('Valor (R$)')
            worksheet.set_column(col_idx, col_idx, 15, money_fmt)
        except: pass

        # Aba Capa
        worksheet_capa = workbook.add_worksheet('Resumo')
        worksheet_capa.write('A1', f"Relatório Gerado em: {datetime.datetime.now()}")
        try:
            worksheet_capa.insert_image('A3', 'logo-brasil-digital.png', {'x_scale': 0.5, 'y_scale': 0.5})
        except: pass
        
    return output.getvalue()
